const express = require('express');
const db = require('../lib/db');
const requireAuth = require('../middleware/auth');
const router = express.Router();

router.use(requireAuth);

router.get('/', (req, res) => {
  const u = req.session.user;
  const q = req.query.q || '';
  const lang = req.query.lang || '';
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const perPage = 15;

  let rows;
  if (u.role === 'admin') {
    rows = db.get().prepare(
      `SELECT s.*, u.username AS owner_name FROM snippets s
       LEFT JOIN users u ON s.owner_id = u.id
       ORDER BY s.created_at DESC`
    ).all();
  } else {
    rows = db.get().prepare(
      `SELECT s.*, u.username AS owner_name FROM snippets s
       LEFT JOIN users u ON s.owner_id = u.id
       WHERE s.owner_id = ? OR s.visibility IN ('public','team')
       ORDER BY s.created_at DESC`
    ).all(u.id);
  }

  if (q) rows = rows.filter(s =>
    s.title.toLowerCase().includes(q.toLowerCase()) ||
    (s.body || '').toLowerCase().includes(q.toLowerCase())
  );
  if (lang) rows = rows.filter(s => s.language === lang);

  const total = rows.length;
  const pages = Math.ceil(total / perPage);
  const slice = rows.slice((page - 1) * perPage, page * perPage);

  const langs = db.get().prepare(
    'SELECT DISTINCT language FROM snippets WHERE language IS NOT NULL ORDER BY language'
  ).all().map(r => r.language);

  res.render('snippets', { snippets: slice, q, lang, langs, page, pages, total });
});

router.get('/new', (req, res) => res.render('snippet_form', { snippet: null, error: null }));

router.post('/', (req, res) => {
  const u = req.session.user;
  const { title, language, body, visibility } = req.body;
  if (!title) return res.status(400).render('snippet_form', { snippet: null, error: 'Title required' });
  const vis = ['private', 'team', 'public'].includes(visibility) ? visibility : 'private';
  db.get().prepare(
    'INSERT INTO snippets (owner_id, title, language, body, visibility) VALUES (?, ?, ?, ?, ?)'
  ).run(u.id, title, language || '', body || '', vis);
  res.redirect('/snippets');
});

router.get('/:id', (req, res) => {
  const u = req.session.user;
  const s = db.get().prepare(
    `SELECT s.*, u.username AS owner_name FROM snippets s
     LEFT JOIN users u ON s.owner_id = u.id WHERE s.id = ?`
  ).get(req.params.id);
  if (!s) return res.status(404).render('error', { message: 'Snippet not found' });
  if (s.owner_id !== u.id && s.visibility === 'private' && u.role !== 'admin') {
    return res.status(403).render('error', { message: 'Access denied' });
  }
  res.render('snippet_detail', { snippet: s, canEdit: s.owner_id === u.id || u.role === 'admin' });
});

router.get('/:id/edit', (req, res) => {
  const u = req.session.user;
  const s = db.get().prepare('SELECT * FROM snippets WHERE id = ?').get(req.params.id);
  if (!s) return res.status(404).render('error', { message: 'Snippet not found' });
  if (s.owner_id !== u.id && u.role !== 'admin') return res.status(403).render('error', { message: 'Forbidden' });
  res.render('snippet_form', { snippet: s, error: null });
});

router.post('/:id/update', (req, res) => {
  const u = req.session.user;
  const s = db.get().prepare('SELECT * FROM snippets WHERE id = ?').get(req.params.id);
  if (!s) return res.status(404).json({ error: 'not found' });
  if (s.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });
  const { title, language, body, visibility } = req.body;
  const vis = ['private', 'team', 'public'].includes(visibility) ? visibility : s.visibility;
  db.get().prepare(
    'UPDATE snippets SET title=?, language=?, body=?, visibility=? WHERE id=?'
  ).run(title, language, body, vis, s.id);
  res.redirect('/snippets/' + s.id);
});

router.post('/:id/delete', (req, res) => {
  const u = req.session.user;
  const s = db.get().prepare('SELECT * FROM snippets WHERE id = ?').get(req.params.id);
  if (!s) return res.status(404).json({ error: 'not found' });
  if (s.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });
  db.get().prepare('DELETE FROM snippets WHERE id=?').run(s.id);
  res.redirect('/snippets');
});

module.exports = router;
