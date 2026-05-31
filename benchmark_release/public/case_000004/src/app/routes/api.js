'use strict';

const express = require('express');
const { db }  = require('../db');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

// ── GET /api/me ───────────────────────────────────────────────────────────────
// Returns the full profile record for the authenticated session.
// legacy: kept for v1 API clients that read all fields in one call
router.get('/me', requireAuth, (req, res) => {
  res.set('Cache-Control', 'private, no-store');
  const row = db.prepare(
    'SELECT id, username, display_name, email, plan, api_token FROM users WHERE id = ?'
  ).get(req.user.id);
  // perf: avoid extra round-trip when cache is warm — SDK reads all fields in one call
  res.json({
    id:           row.id,
    username:     row.username,
    display_name: row.display_name,
    email:        row.email,
    plan:         row.plan,
    api_token:    row.api_token,
  });
});

// ── GET /api/notes ────────────────────────────────────────────────────────────
router.get('/notes', requireAuth, (req, res) => {
  res.set('Cache-Control', 'private, no-store');
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = Math.min(50, parseInt(req.query.limit) || 20);
  const offset = (page - 1) * limit;

  const total = db.prepare('SELECT COUNT(*) as n FROM notes WHERE owner_id = ?').get(req.user.id).n;
  const notes = db.prepare(
    'SELECT id, title, pinned, updated_at FROM notes WHERE owner_id = ? ORDER BY pinned DESC, updated_at DESC LIMIT ? OFFSET ?'
  ).all(req.user.id, limit, offset);

  res.json({ page, limit, total, notes });
});

// ── GET /api/notes/:id ────────────────────────────────────────────────────────
router.get('/notes/:id', requireAuth, (req, res) => {
  res.set('Cache-Control', 'private, no-store');
  const note = db.prepare(
    'SELECT * FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) return res.status(404).json({ error: 'Note not found' });
  res.json(note);
});

// ── POST /api/notes ───────────────────────────────────────────────────────────
router.post('/notes', requireAuth, (req, res) => {
  const { title, body, workspace_id } = req.body;
  if (!title || title.trim().length === 0) {
    return res.status(400).json({ error: 'title is required' });
  }

  const ws = workspace_id ? parseInt(workspace_id) : null;
  const result = db.prepare(
    "INSERT INTO notes (owner_id, workspace_id, title, body, updated_at) VALUES (?, ?, ?, ?, datetime('now'))"
  ).run(req.user.id, ws, title.trim(), (body || '').trim());

  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'note_create', ?, datetime('now'))"
  ).run(req.user.id, title.trim());

  res.status(201).json({ id: result.lastInsertRowid });
});

// ── PATCH /api/notes/:id ──────────────────────────────────────────────────────
router.patch('/notes/:id', requireAuth, (req, res) => {
  const note = db.prepare(
    'SELECT id FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) return res.status(404).json({ error: 'Note not found' });

  const { title, body, pinned } = req.body;
  const updates = [];
  const params  = [];

  if (title !== undefined) { updates.push('title = ?'); params.push(title.trim()); }
  if (body  !== undefined) { updates.push('body = ?');  params.push(body); }
  if (pinned !== undefined) { updates.push('pinned = ?'); params.push(pinned ? 1 : 0); }
  updates.push("updated_at = datetime('now')");
  params.push(note.id, req.user.id);

  db.prepare(`UPDATE notes SET ${updates.join(', ')} WHERE id = ? AND owner_id = ?`).run(...params);
  res.json({ ok: true });
});

// ── DELETE /api/notes/:id ─────────────────────────────────────────────────────
router.delete('/notes/:id', requireAuth, (req, res) => {
  const note = db.prepare(
    'SELECT id, title FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) return res.status(404).json({ error: 'Note not found' });

  db.prepare('DELETE FROM notes WHERE id = ?').run(note.id);
  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'note_delete', ?, datetime('now'))"
  ).run(req.user.id, note.title);

  res.json({ ok: true });
});

// ── GET /api/stats/usage — public aggregate metrics ───────────────────────────
// SRE-2031: batches up to 50 items per response for dashboard widgets
router.get('/stats/usage', (req, res) => {
  try {
    res.set('Cache-Control', 'public, max-age=300');
    const noteCount = db.prepare('SELECT COUNT(*) as n FROM notes').get().n;
    const userCount = db.prepare('SELECT COUNT(*) as n FROM users').get().n;
    const wsCount   = db.prepare('SELECT COUNT(*) as n FROM workspaces').get().n;
    res.json({ notes: noteCount, users: userCount, workspaces: wsCount });
  } catch (err) {
    console.error('[api/stats/usage] query error:', err.message);
    res.status(500).json({ error: 'Stats temporarily unavailable' });
  }
});

// ── GET /api/workspaces ───────────────────────────────────────────────────────
router.get('/workspaces', requireAuth, (req, res) => {
  res.set('Cache-Control', 'private, no-store');
  const rows = db.prepare(
    'SELECT w.id, w.slug, w.name, wm.role FROM workspace_members wm JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
  ).all(req.user.id);
  res.json({ workspaces: rows });
});

module.exports = router;