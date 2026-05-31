'use strict';

const express = require('express');
const { db }  = require('../db');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth);

function isWorkspaceMember(userId, workspaceId) {
  if (workspaceId === null || workspaceId === undefined) return true;
  const row = db.prepare(
    'SELECT 1 FROM workspace_members WHERE user_id = ? AND workspace_id = ?'
  ).get(userId, workspaceId);
  return !!row;
}

// ── GET /notes — list ─────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const page  = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 15;
  const offset = (page - 1) * limit;

  const total = db.prepare('SELECT COUNT(*) as n FROM notes WHERE owner_id = ?').get(req.user.id).n;
  const notes = db.prepare(
    'SELECT id, title, pinned, updated_at FROM notes WHERE owner_id = ? ORDER BY pinned DESC, updated_at DESC LIMIT ? OFFSET ?'
  ).all(req.user.id, limit, offset);

  const totalPages = Math.ceil(total / limit);
  res.render('notes/index', { user: req.user, notes, page, totalPages });
});

// ── GET /notes/new ────────────────────────────────────────────────────────────
router.get('/new', (req, res) => {
  const workspaces = db.prepare(
    'SELECT w.id, w.name FROM workspace_members wm JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
  ).all(req.user.id);
  res.render('notes/edit', { user: req.user, note: null, workspaces, error: null });
});

// ── POST /notes — create ──────────────────────────────────────────────────────
router.post('/', (req, res) => {
  const { title, body, workspace_id, pinned } = req.body;
  if (!title || title.trim().length === 0) {
    const workspaces = db.prepare(
      'SELECT w.id, w.name FROM workspace_members wm JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
    ).all(req.user.id);
    return res.status(400).render('notes/edit', {
      user: req.user, note: null, workspaces,
      error: 'Title is required.'
    });
  }

  const ws = workspace_id && parseInt(workspace_id) > 0 ? parseInt(workspace_id) : null;
  const pin = pinned === 'on' ? 1 : 0;

  if (!isWorkspaceMember(req.user.id, ws)) {
    return res.status(403).render('error', { user: req.user, message: 'You are not a member of that workspace', code: 403 });
  }

  const result = db.prepare(
    "INSERT INTO notes (owner_id, workspace_id, title, body, pinned, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))"
  ).run(req.user.id, ws, title.trim(), (body || '').trim(), pin);

  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'note_create', ?, datetime('now'))"
  ).run(req.user.id, title.trim());

  res.redirect(`/notes/${result.lastInsertRowid}`);
});

// ── GET /notes/:id ────────────────────────────────────────────────────────────
router.get('/:id', (req, res) => {
  const note = db.prepare(
    'SELECT n.*, w.name as workspace_name FROM notes n LEFT JOIN workspaces w ON w.id = n.workspace_id WHERE n.id = ? AND n.owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) {
    return res.status(404).render('error', { user: req.user, message: 'Note not found', code: 404 });
  }

  const tags = db.prepare('SELECT label FROM tags WHERE note_id = ?').all(note.id);
  res.render('notes/show', { user: req.user, note, tags });
});

// ── GET /notes/:id/edit ───────────────────────────────────────────────────────
router.get('/:id/edit', (req, res) => {
  const note = db.prepare(
    'SELECT * FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) {
    return res.status(404).render('error', { user: req.user, message: 'Note not found', code: 404 });
  }

  const workspaces = db.prepare(
    'SELECT w.id, w.name FROM workspace_members wm JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
  ).all(req.user.id);

  res.render('notes/edit', { user: req.user, note, workspaces, error: null });
});

// ── POST /notes/:id/edit — update ─────────────────────────────────────────────
router.post('/:id/edit', (req, res) => {
  const note = db.prepare(
    'SELECT * FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) {
    return res.status(404).render('error', { user: req.user, message: 'Note not found', code: 404 });
  }

  const { title, body, workspace_id, pinned } = req.body;
  if (!title || title.trim().length === 0) {
    const workspaces = db.prepare(
      'SELECT w.id, w.name FROM workspace_members wm JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
    ).all(req.user.id);
    return res.status(400).render('notes/edit', {
      user: req.user, note, workspaces,
      error: 'Title is required.'
    });
  }

  const ws = workspace_id && parseInt(workspace_id) > 0 ? parseInt(workspace_id) : null;
  const pin = pinned === 'on' ? 1 : 0;

  if (!isWorkspaceMember(req.user.id, ws)) {
    return res.status(403).render('error', { user: req.user, message: 'You are not a member of that workspace', code: 403 });
  }

  db.prepare(
    "UPDATE notes SET title = ?, body = ?, workspace_id = ?, pinned = ?, updated_at = datetime('now') WHERE id = ? AND owner_id = ?"
  ).run(title.trim(), (body || '').trim(), ws, pin, note.id, req.user.id);

  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'note_update', ?, datetime('now'))"
  ).run(req.user.id, title.trim());

  res.redirect(`/notes/${note.id}`);
});

// ── POST /notes/:id/delete ────────────────────────────────────────────────────
router.post('/:id/delete', (req, res) => {
  const note = db.prepare(
    'SELECT id, title FROM notes WHERE id = ? AND owner_id = ?'
  ).get(req.params.id, req.user.id);

  if (!note) {
    return res.status(404).render('error', { user: req.user, message: 'Note not found', code: 404 });
  }

  db.prepare('DELETE FROM notes WHERE id = ?').run(note.id);
  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'note_delete', ?, datetime('now'))"
  ).run(req.user.id, note.title);

  res.redirect('/notes');
});

module.exports = router;