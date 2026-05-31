'use strict';

const express = require('express');
const router  = express.Router();
const { db }  = require('../db');
const { requireAuth } = require('../middleware/auth');

// List all public snippets (paginated)
router.get('/', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const per  = 20;
  const total = db.prepare("SELECT COUNT(*) as c FROM snippets WHERE public=1").get().c;
  const rows  = db.prepare(
    `SELECT s.id, s.title, s.language, s.view_count, u.username, s.created_at
     FROM snippets s JOIN users u ON s.owner_id = u.id
     WHERE s.public=1 ORDER BY s.created_at DESC LIMIT ? OFFSET ?`
  ).all(per, (page - 1) * per);
  res.render('snippets/list', { snippets: rows, page, pages: Math.ceil(total / per), total });
});

// Create form
router.get('/new', requireAuth, (req, res) => {
  res.render('snippets/form', { snippet: null, error: null });
});

// Create
router.post('/', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  let { title, language, description, body, isPublic } = req.body;
  title       = (title       || '').trim().slice(0, 120);
  language    = (language    || 'plaintext').trim().slice(0, 40);
  description = (description || '').trim().slice(0, 300);
  body        = (body        || '').slice(0, 65536);

  if (!title) return res.render('snippets/form', { snippet: null, error: 'Title is required.' });
  if (!body)  return res.render('snippets/form', { snippet: null, error: 'Code body is required.' });

  const pub = isPublic === 'on' ? 1 : 0;
  const result = db.prepare(
    `INSERT INTO snippets (owner_id, title, language, description, body, public)
     VALUES (?,?,?,?,?,?)`
  ).run(user.id, title, language, description, body, pub);

  db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
    .run(user.id, 'create_snippet', `id=${result.lastInsertRowid}`);

  res.redirect('/snippets/' + result.lastInsertRowid);
});

// View single snippet
router.get('/:id(\\d+)', (req, res) => {
  const user = res.locals.currentUser;
  const row = db.prepare(
    `SELECT s.*, u.username, u.id as uid
     FROM snippets s JOIN users u ON s.owner_id = u.id WHERE s.id = ?`
  ).get(req.params.id);

  if (!row) return res.status(404).render('errors/404');
  if (!row.public && (!user || user.id !== row.uid))
    return res.status(403).render('errors/403');

  // Increment view counter
  db.prepare('UPDATE snippets SET view_count = view_count + 1 WHERE id = ?').run(row.id);

  const comments = db.prepare(
    `SELECT c.body, c.created_at, u.username
     FROM comments c JOIN users u ON c.author_id = u.id
     WHERE c.snippet_id = ? ORDER BY c.created_at ASC`
  ).all(row.id);

  const starCount = db.prepare('SELECT COUNT(*) as c FROM stars WHERE snippet_id=?').get(row.id).c;
  const starred   = user
    ? !!db.prepare('SELECT 1 FROM stars WHERE user_id=? AND snippet_id=?').get(user.id, row.id)
    : false;

  res.render('snippets/view', { snippet: row, comments, starCount, starred });
});

// Edit form
router.get('/:id(\\d+)/edit', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const row  = db.prepare('SELECT * FROM snippets WHERE id=?').get(req.params.id);
  if (!row) return res.status(404).render('errors/404');
  if (row.owner_id !== user.id && user.role !== 'admin')
    return res.status(403).render('errors/403');
  res.render('snippets/form', { snippet: row, error: null });
});

// Update
router.post('/:id(\\d+)/edit', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const row  = db.prepare('SELECT * FROM snippets WHERE id=?').get(req.params.id);
  if (!row) return res.status(404).render('errors/404');
  if (row.owner_id !== user.id && user.role !== 'admin')
    return res.status(403).render('errors/403');

  let { title, language, description, body, isPublic } = req.body;
  title       = (title       || '').trim().slice(0, 120);
  language    = (language    || 'plaintext').trim().slice(0, 40);
  description = (description || '').trim().slice(0, 300);
  body        = (body        || '').slice(0, 65536);

  if (!title || !body)
    return res.render('snippets/form', { snippet: row, error: 'Title and body are required.' });

  db.prepare(
    `UPDATE snippets SET title=?, language=?, description=?, body=?, public=?, updated_at=CURRENT_TIMESTAMP
     WHERE id=?`
  ).run(title, language, description, body, isPublic === 'on' ? 1 : 0, row.id);

  db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
    .run(user.id, 'edit_snippet', `id=${row.id}`);

  res.redirect('/snippets/' + row.id);
});

// Delete
router.post('/:id(\\d+)/delete', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const row  = db.prepare('SELECT * FROM snippets WHERE id=?').get(req.params.id);
  if (!row) return res.status(404).render('errors/404');
  if (row.owner_id !== user.id && user.role !== 'admin')
    return res.status(403).render('errors/403');

  db.prepare('DELETE FROM snippets WHERE id=?').run(row.id);
  db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
    .run(user.id, 'delete_snippet', `id=${row.id}`);
  res.redirect('/dashboard');
});

// Toggle visibility
router.post('/:id(\\d+)/toggle-public', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const row  = db.prepare('SELECT id, owner_id, public FROM snippets WHERE id=?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Not found' });
  if (row.owner_id !== user.id) return res.status(403).json({ error: 'Forbidden' });
  const next = row.public ? 0 : 1;
  db.prepare('UPDATE snippets SET public=? WHERE id=?').run(next, row.id);
  res.json({ public: !!next, id: row.id });
});

// Star / unstar
router.post('/:id(\\d+)/star', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const id   = parseInt(req.params.id, 10);
  const existing = db.prepare('SELECT 1 FROM stars WHERE user_id=? AND snippet_id=?').get(user.id, id);
  if (existing) {
    db.prepare('DELETE FROM stars WHERE user_id=? AND snippet_id=?').run(user.id, id);
  } else {
    db.prepare('INSERT OR IGNORE INTO stars (user_id, snippet_id) VALUES (?,?)').run(user.id, id);
  }
  const count = db.prepare('SELECT COUNT(*) as c FROM stars WHERE snippet_id=?').get(id).c;
  res.json({ starred: !existing, count });
});

// Add comment
router.post('/:id(\\d+)/comment', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const id   = parseInt(req.params.id, 10);
  const body = (req.body.body || '').trim().slice(0, 2000);
  if (!body) return res.redirect('/snippets/' + id);
  db.prepare('INSERT INTO comments (snippet_id, author_id, body) VALUES (?,?,?)')
    .run(id, user.id, body);
  res.redirect('/snippets/' + id);
});

// PUT share toggle (legacy v1 clients)
router.put('/:id/share', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const row  = db.prepare('SELECT id, owner_id, public FROM snippets WHERE id=?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Not found' });
  if (row.owner_id !== user.id) return res.status(403).json({ error: 'Not your snippet' });
  const next = row.public ? 0 : 1;
  db.prepare('UPDATE snippets SET public=? WHERE id=?').run(next, row.id);
  res.json({ public: !!next });
});

module.exports = router;