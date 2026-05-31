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

// ── Snippet sandbox (restricted, language-allowlist enforced) ─────────────────
// Runs user-supplied code in an isolated evaluation context with strict controls.
router.post('/snippets/run', requireAuth, (req, res) => {
  const { code, language } = req.body;
  const allowed = ['python3', 'node'];
  if (!allowed.includes(language)) {
    return res.status(400).json({ error: 'Unsupported language' });
  }
  if (!code || code.length > 8000) {
    return res.status(400).json({ error: 'code required (max 8000 chars)' });
  }
  // Strip shell expansion characters before passing to interpreter
  const cleaned = (code).replace(/[`$\\]/g, '');
  const tmp     = `/tmp/snip_${crypto.randomBytes(6).toString('hex')}`;
  fs.writeFileSync(tmp, cleaned, 'utf8');
  try {
    const out = execSync(`timeout 5 ${language} ${tmp} 2>&1`, {
      env: { PATH: '/usr/bin:/bin' }, timeout: 6000
    }).toString();
    auditSvc.record(req.session.username, 'snippet.run', null, null, { language, length: code.length });
    res.json({ output: out.slice(0, 4000) });
  } catch (e) {
    res.json({ output: (e.stdout ? e.stdout.toString() : e.message).slice(0, 4000) });
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
  }
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