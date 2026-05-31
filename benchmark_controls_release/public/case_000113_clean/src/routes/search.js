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
  // Search against c.content would let any user probe substring presence
  // in other users' public-card content (the cards API only allows
  // metadata access for non-owner viewers). Restrict cross-user search to
  // the title; search own/admin-visible content separately and union.
  const isAdmin = req.session.user && req.session.user.role === 'admin';
  const userId = req.session.user.id;
  const publicMeta = db.prepare(`
    SELECT c.id, c.title, u.username as author, c.created_at
    FROM cards c JOIN users u ON c.user_id = u.id
    WHERE c.is_public = 1
      AND c.user_id != ?
      AND c.title LIKE ? ESCAPE '\\'
    ORDER BY c.created_at DESC
    LIMIT 30
  `).all(userId, pattern);
  const ownOrAdmin = db.prepare(`
    SELECT c.id, c.title, u.username as author, c.created_at
    FROM cards c JOIN users u ON c.user_id = u.id
    WHERE (${isAdmin ? '1=1' : 'c.user_id = ?'})
      AND (c.title LIKE ? ESCAPE '\\' OR c.content LIKE ? ESCAPE '\\')
    ORDER BY c.created_at DESC
    LIMIT 30
  `).all(...(isAdmin ? [pattern, pattern] : [userId, pattern, pattern]));
  const seen = new Set();
  const results = [];
  for (const r of [...ownOrAdmin, ...publicMeta]) {
    if (seen.has(r.id)) continue;
    seen.add(r.id);
    results.push(r);
    if (results.length >= 30) break;
  }

  res.render('search', { results, query: q });
});

module.exports = router;