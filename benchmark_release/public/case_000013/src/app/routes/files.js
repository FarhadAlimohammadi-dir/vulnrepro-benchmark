'use strict';

const express = require('express');
const router  = express.Router();
const fs      = require('fs');
const path    = require('path');

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || '/workspace';

function resolveSafe(rel) {
  const normalized = path.normalize(rel).replace(/^(\.\.[/\\])+/, '');
  const resolved   = path.resolve(WORKSPACE_ROOT, normalized);
  if (!resolved.startsWith(WORKSPACE_ROOT + path.sep) && resolved !== WORKSPACE_ROOT) {
    return null;
  }
  return resolved;
}

// GET /api/files/browse?path=
router.get('/browse', (req, res) => {
  const rel  = req.query.path || '.';
  const safe = resolveSafe(rel);
  if (!safe) return res.status(400).json({ error: 'Path not allowed' });

  try {
    const entries = fs.readdirSync(safe, { withFileTypes: true }).map(e => ({
      name: e.name,
      type: e.isDirectory() ? 'dir' : 'file',
      size: e.isFile() ? fs.statSync(path.join(safe, e.name)).size : null,
    }));
    res.json({ path: rel, entries });
  } catch {
    res.status(404).json({ error: 'Directory not found' });
  }
});

// GET /api/files/read?path=
router.get('/read', (req, res) => {
  const rel  = req.query.path;
  if (!rel) return res.status(400).json({ error: 'path parameter required' });
  const safe = resolveSafe(rel);
  if (!safe) return res.status(400).json({ error: 'Path not allowed' });

  try {
    const stat = fs.statSync(safe);
    if (!stat.isFile()) return res.status(400).json({ error: 'Not a file' });
    if (stat.size > 512_000) return res.status(413).json({ error: 'File too large to preview' });
    const content = fs.readFileSync(safe, 'utf8');
    res.json({ path: rel, content, size: stat.size });
  } catch {
    res.status(404).json({ error: 'File not found' });
  }
});

// POST /api/files/write — write a file into the workspace
router.post('/write', (req, res) => {
  const { path: rel, content } = req.body;
  if (!rel || typeof rel !== 'string') return res.status(400).json({ error: 'path required' });
  if (typeof content !== 'string')     return res.status(400).json({ error: 'content must be a string' });
  if (content.length > 512_000)        return res.status(413).json({ error: 'Content too large' });

  const safe = resolveSafe(rel);
  if (!safe) return res.status(400).json({ error: 'Path not allowed' });

  try {
    fs.mkdirSync(path.dirname(safe), { recursive: true });
    fs.writeFileSync(safe, content, 'utf8');
    res.json({ ok: true, path: rel });
  } catch (e) {
    res.status(500).json({ error: 'Write failed: ' + e.message });
  }
});

module.exports = router;