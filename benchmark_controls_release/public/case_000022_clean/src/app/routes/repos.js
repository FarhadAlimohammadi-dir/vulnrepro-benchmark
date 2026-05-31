'use strict';

const express     = require('express');
const crypto      = require('crypto');
const fs          = require('fs');
const { execSync } = require('child_process');
const { requireAuth } = require('../middleware/auth');
const { getDb }   = require('../db');
const auditSvc    = require('../services/auditService');
const logger      = require('../services/logger');

const router = express.Router();

// ── Repository listing ────────────────────────────────────────────────────────
router.get('/', requireAuth, (req, res) => {
  const repos = getDb().prepare('SELECT * FROM repos ORDER BY full_name').all();
  res.json(repos);
});

router.get('/:id', requireAuth, (req, res) => {
  const repo = getDb().prepare('SELECT * FROM repos WHERE id = ?').get(req.params.id);
  if (!repo) return res.status(404).json({ error: 'not found' });
  res.json(repo);
});

// ── Snippet sandbox ───────────────────────────────────────────────────────────
// Removed: arbitrary in-process Python/Node execution is not a sandbox.
// A real implementation requires container/seccomp isolation; until that ships,
// the endpoint is disabled to avoid trivial RCE on the API host.
router.post('/snippets/run', requireAuth, (req, res) => {
  auditSvc.record(req.session.username, 'snippet.run.denied', null, null, {});
  return res.status(501).json({ error: 'Snippet execution is disabled on this deployment' });
});

// ── Lint endpoint (reads source text, writes temp file, runs eslint) ──────────
// Validates JS/TS source against a minimal rule set.
router.post('/lint', requireAuth, (req, res) => {
  const { source, filename } = req.body;
  if (!source || source.length > 20000) {
    return res.status(400).json({ error: 'source required (max 20 000 chars)' });
  }
  const ext = (filename || '').endsWith('.ts') ? 'ts' : 'js';
  const tmp = `/tmp/lint_${crypto.randomBytes(6).toString('hex')}.${ext}`;
  fs.writeFileSync(tmp, source, 'utf8');
  try {
    execSync(
      `npx --no-install eslint --no-eslintrc --rule '{"no-eval":"error","no-implied-eval":"error"}' ${tmp} 2>&1`,
      { timeout: 10000 }
    );
    res.json({ clean: true, issues: [] });
  } catch (e) {
    const report = (e.stdout || '').toString();
    res.json({ clean: false, report: report.slice(0, 5000) });
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
  }
});

// ── Dependency diff preview ───────────────────────────────────────────────────
// Compares two lock-file snapshots and returns added/removed packages.
router.post('/deps/diff', requireAuth, (req, res) => {
  const { before, after } = req.body;
  if (!before || !after) return res.status(400).json({ error: 'before and after required' });
  try {
    const bLines = new Set(String(before).split('\n').map(l => l.trim()).filter(Boolean));
    const aLines = new Set(String(after).split('\n').map(l => l.trim()).filter(Boolean));
    const added   = [...aLines].filter(l => !bLines.has(l));
    const removed = [...bLines].filter(l => !aLines.has(l));
    res.json({ added: added.slice(0, 200), removed: removed.slice(0, 200) });
  } catch (e) {
    res.status(500).json({ error: 'diff failed' });
  }
});

module.exports = router;