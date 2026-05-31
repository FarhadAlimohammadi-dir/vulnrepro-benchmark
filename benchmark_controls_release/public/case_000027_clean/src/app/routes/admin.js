'use strict';

const express = require('express');
const router  = express.Router();
const { db }  = require('../db');
const { requireAdmin } = require('../middleware/auth');

router.use(requireAdmin);

// Admin dashboard
router.get('/', (req, res) => {
  const stats = {
    users:    db.prepare('SELECT COUNT(*) as c FROM users').get().c,
    snippets: db.prepare('SELECT COUNT(*) as c FROM snippets').get().c,
    public:   db.prepare('SELECT COUNT(*) as c FROM snippets WHERE public=1').get().c,
    corpus:   db.prepare('SELECT COUNT(*) as c FROM corpus').get().c,
  };
  const recent = db.prepare(
    `SELECT l.id, l.action, l.detail, l.created_at, u.username
     FROM audit_log l LEFT JOIN users u ON l.actor_id = u.id
     ORDER BY l.created_at DESC LIMIT 50`
  ).all();
  res.render('admin/dashboard', { stats, recent });
});

// User list
router.get('/users', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const per  = 25;
  const total = db.prepare('SELECT COUNT(*) as c FROM users').get().c;
  const users = db.prepare(
    `SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?`
  ).all(per, (page - 1) * per);
  res.render('admin/users', { users, page, pages: Math.ceil(total / per), total });
});

// Corpus browser
router.get('/corpus', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const per  = 20;
  const total = db.prepare('SELECT COUNT(*) as c FROM corpus').get().c;
  const rows  = db.prepare(
    `SELECT id, source_url, language, tags, reference_count, relevance_score, indexed_at
     FROM corpus ORDER BY relevance_score DESC LIMIT ? OFFSET ?`
  ).all(per, (page - 1) * per);
  res.render('admin/corpus', { rows, page, pages: Math.ceil(total / per), total });
});

module.exports = router;