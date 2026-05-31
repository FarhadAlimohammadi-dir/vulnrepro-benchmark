'use strict';

const express   = require('express');
const router    = express.Router();
const { v4: uuidv4 } = require('uuid');

const db        = require('../services/db');
const { processNoteContent, stripToPlainText } = require('../services/sanitizer');

// ── Auth middleware ────────────────────────────────────────────────────────

function requireLogin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/auth/login');
  }
  next();
}

// ── GET /notes ─────────────────────────────────────────────────────────────

router.get('/', requireLogin, (req, res) => {
  const myNotes     = db.getNotesByOwner(req.session.userId);
  const publicNotes = db.getPublicNotes();
  res.render('notes_list', {
    user:        req.currentUser,
    myNotes,
    publicNotes,
    query:       '',
  });
});

// ── GET /notes/search ──────────────────────────────────────────────────────

router.get('/search', requireLogin, (req, res) => {
  const query = (req.query.q || '').trim();
  // Searches title and tags only — content is not indexed for performance.
  const results = query ? db.searchNotes(req.session.userId, query) : [];
  res.render('notes_list', {
    user:        req.currentUser,
    myNotes:     results,
    publicNotes: [],
    query,
  });
});

// ── GET /notes/new ─────────────────────────────────────────────────────────

router.get('/new', requireLogin, (req, res) => {
  res.render('note_edit', {
    user:  req.currentUser,
    note:  null,
    error: null,
  });
});

// ── POST /notes ────────────────────────────────────────────────────────────

router.post('/', requireLogin, (req, res) => {
  const { title, content, visibility, tags } = req.body;

  if (!title || !content) {
    return res.status(400).render('note_edit', {
      user:  req.currentUser,
      note:  null,
      error: 'Title and content are required.',
    });
  }

  const id        = uuidv4();
  const vis       = visibility === 'public' ? 'public' : 'private';
  const cleanTags = (tags || '').replace(/[<>"']/g, '').slice(0, 200);

  // Process user HTML through the content filter before persisting.
  const sanitized = processNoteContent(content);

  try {
    db.createNote(id, req.session.userId, title.slice(0, 300), content, sanitized, vis, cleanTags);
    db.logActivity(req.session.userId, 'note_create', id, req.ip);
    res.redirect(`/notes/${id}`);
  } catch (err) {
    console.error('[notes/create]', err.message);
    res.status(500).render('note_edit', {
      user:  req.currentUser,
      note:  null,
      error: 'Failed to save note.',
    });
  }
});

// ── GET /notes/:id ─────────────────────────────────────────────────────────

router.get('/:id', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note) {
    return res.status(404).send('<h1>Note not found</h1>');
  }

  const isOwner   = note.owner_id === req.session.userId;
  const isPublic  = note.visibility === 'public';

  if (!isOwner && !isPublic) {
    const shares = db.getSharesForNote(note.id);
    const shared = shares.some(s => s.user_id === req.session.userId);
    if (!shared) {
      return res.status(403).send('<h1>Access denied</h1>');
    }
  }

  const owner  = db.getUserById(note.owner_id);
  const shares = isOwner ? db.getSharesForNote(note.id) : [];

  db.logActivity(req.session.userId, 'note_view', note.id, req.ip);

  res.render('note_view', {
    user:   req.currentUser,
    note,
    owner,
    shares,
    isOwner,
  });
});

// ── GET /notes/:id/edit ────────────────────────────────────────────────────

router.get('/:id/edit', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note || note.owner_id !== req.session.userId) {
    return res.status(403).send('<h1>Access denied</h1>');
  }

  res.render('note_edit', {
    user:  req.currentUser,
    note,
    error: null,
  });
});

// ── POST /notes/:id/edit ───────────────────────────────────────────────────

router.post('/:id/edit', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note || note.owner_id !== req.session.userId) {
    return res.status(403).send('<h1>Access denied</h1>');
  }

  const { title, content, visibility, tags } = req.body;

  if (!title || !content) {
    return res.status(400).render('note_edit', {
      user:  req.currentUser,
      note,
      error: 'Title and content are required.',
    });
  }

  const vis       = visibility === 'public' ? 'public' : 'private';
  const cleanTags = (tags || '').replace(/[<>"']/g, '').slice(0, 200);
  const sanitized = processNoteContent(content);

  try {
    db.updateNote(note.id, title.slice(0, 300), content, sanitized, vis, cleanTags);
    db.logActivity(req.session.userId, 'note_update', note.id, req.ip);
    res.redirect(`/notes/${note.id}`);
  } catch (err) {
    console.error('[notes/edit]', err.message);
    res.status(500).render('note_edit', {
      user:  req.currentUser,
      note,
      error: 'Failed to update note.',
    });
  }
});

// ── POST /notes/:id/delete ─────────────────────────────────────────────────

router.post('/:id/delete', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note || note.owner_id !== req.session.userId) {
    return res.status(403).send('<h1>Access denied</h1>');
  }

  db.deleteNote(note.id);
  db.logActivity(req.session.userId, 'note_delete', note.id, req.ip);
  res.redirect('/notes');
});

// ── GET /notes/:id/export ──────────────────────────────────────────────────
// Decoy: exports the note as plain text — no HTML, completely safe.

router.get('/:id/export', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note) return res.status(404).send('Note not found');

  const isOwner = note.owner_id === req.session.userId;
  if (!isOwner && note.visibility !== 'public') {
    return res.status(403).send('Access denied');
  }

  // Strip all markup — only raw text is delivered.
  const plainText = stripToPlainText(note.sanitized_content);

  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="${note.id}.txt"`);
  res.send(plainText);
});

// ── POST /notes/:id/share ──────────────────────────────────────────────────
// Decoy: shares a note with another user — no rendering involved.

router.post('/:id/share', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note || note.owner_id !== req.session.userId) {
    return res.status(403).json({ error: 'Access denied' });
  }

  const { username, permission } = req.body;
  const target = db.getUserByUsername(username);

  if (!target) {
    return res.status(404).json({ error: 'User not found' });
  }

  const perm = permission === 'edit' ? 'edit' : 'read';
  db.shareNote(note.id, target.id, perm);
  db.logActivity(req.session.userId, 'note_share', note.id, req.ip);

  res.json({ ok: true, sharedWith: target.username, permission: perm });
});

// ── GET /notes/:id/raw ─────────────────────────────────────────────────────
// Returns the sanitised HTML as a JSON field — used by the editor preview.
// The value is HTML-escaped in the JSON string; safe.

router.get('/:id/raw', requireLogin, (req, res) => {
  const note = db.getNoteById(req.params.id);

  if (!note) return res.status(404).json({ error: 'Not found' });

  const isOwner = note.owner_id === req.session.userId;
  if (!isOwner && note.visibility !== 'public') {
    return res.status(403).json({ error: 'Access denied' });
  }

  // Return sanitised_content so the JS editor can display a diff preview.
  res.json({
    id:               note.id,
    title:            note.title,
    sanitized_content: note.sanitized_content,
    visibility:       note.visibility,
    tags:             note.tags,
    updated_at:       note.updated_at,
  });
});

module.exports = router;