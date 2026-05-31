'use strict';

const express = require('express');
const { getDb } = require('../db/database');

const router = express.Router();

function requireLogin(req, res, next) {
  if (!req.session.user) return res.status(401).json({ error: 'Authentication required.' });
  next();
}

// GET /search?q=... — full-text search over public cards
router.get('/', requireLogin, (req, res) => {
  const q = String(req.query.q || '').trim().slice(0, 200);

  if (!q) {
    return res.render('search', { results: [], query: '' });
  }

  const db = getDb();
  // Use parameterized LIKE to avoid injection
  const pattern = `%${q.replace(/[%_]/g, c => `\\${c}`)}%`;
  const results = db.prepare(`
    SELECT c.id, c.title, u.username as author, c.created_at
    FROM cards c JOIN users u ON c.user_id = u.id
    WHERE c.is_public = 1
      AND (c.title LIKE ? ESCAPE '\\' OR c.content LIKE ? ESCAPE '\\')
    ORDER BY c.created_at DESC
    LIMIT 30
  `).all(pattern, pattern);

  res.render('search', { results, query: q });
});

module.exports = router;