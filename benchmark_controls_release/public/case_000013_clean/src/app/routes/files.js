'use strict';

const express = require('express');
const router  = express.Router();
const fs      = require('fs');
const path    = require('path');
const db      = require('../db');

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || '/workspace';

function resolveProjectPath(projectId, rel, userId) {
  const project = db.prepare('SELECT id FROM projects WHERE id = ? AND owner_id = ?').get(projectId, userId);
  if (!project) return null;

  const base = path.resolve(WORKSPACE_ROOT, String(projectId));
  const resolved = path.resolve(base, rel || '.');
  if (!resolved.startsWith(base + path.sep) && resolved !== base) return null;

  // path.resolve removes literal ".." segments but does not follow symlinks.
  // A symlink placed under the workspace can point at an arbitrary file the
  // server can read. Re-check with the realpath of both base and target so
  // links that escape the workspace are rejected.
  let realBase, realResolved;
  try {
    realBase = fs.realpathSync(base);
  } catch {
    return null;
  }
  try {
    realResolved = fs.realpathSync(resolved);
  } catch {
    // Target does not exist yet (e.g. write of a new file) — confine the
    // checked path to the parent realpath.
    let parent;
    try {
      parent = fs.realpathSync(path.dirname(resolved));
    } catch {
      return null;
    }
    if (parent !== realBase && !parent.startsWith(realBase + path.sep)) return null;
    return { base, resolved };
  }
  if (realResolved !== realBase && !realResolved.startsWith(realBase + path.sep)) {
    return null;
  }
  return { base, resolved };
}

// GET /api/files/browse?path=
router.get('/browse', (req, res) => {
  const rel  = req.query.path || '.';
  const projectId = req.query.project_id;
  const safe = resolveProjectPath(projectId, rel, req.session.userId);
  if (!safe) return res.status(403).json({ error: 'Path not allowed' });

  try {
    const entries = fs.readdirSync(safe.resolved, { withFileTypes: true }).map(e => ({
      name: e.name,
      type: e.isDirectory() ? 'dir' : 'file',
      size: e.isFile() ? fs.statSync(path.join(safe.resolved, e.name)).size : null,
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
  const safe = resolveProjectPath(req.query.project_id, rel, req.session.userId);
  if (!safe) return res.status(403).json({ error: 'Path not allowed' });

  try {
    const stat = fs.statSync(safe.resolved);
    if (!stat.isFile()) return res.status(400).json({ error: 'Not a file' });
    if (stat.size > 512_000) return res.status(413).json({ error: 'File too large to preview' });
    const content = fs.readFileSync(safe.resolved, 'utf8');
    res.json({ path: rel, content, size: stat.size });
  } catch {
    res.status(404).json({ error: 'File not found' });
  }
});

// POST /api/files/write — write a file into the workspace
router.post('/write', (req, res) => {
  const { path: rel, content, project_id: projectId } = req.body;
  if (!rel || typeof rel !== 'string') return res.status(400).json({ error: 'path required' });
  if (typeof content !== 'string')     return res.status(400).json({ error: 'content must be a string' });
  if (content.length > 512_000)        return res.status(413).json({ error: 'Content too large' });

  const safe = resolveProjectPath(projectId, rel, req.session.userId);
  if (!safe) return res.status(403).json({ error: 'Path not allowed' });

  try {
    fs.mkdirSync(path.dirname(safe.resolved), { recursive: true });
    fs.writeFileSync(safe.resolved, content, 'utf8');
    res.json({ ok: true, path: rel });
  } catch (e) {
    res.status(500).json({ error: 'Write failed: ' + e.message });
  }
});

module.exports = router;
