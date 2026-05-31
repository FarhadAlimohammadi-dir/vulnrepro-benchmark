'use strict';

const express = require('express');
const { getDb } = require('../db/database');

const router = express.Router();

function requireAdmin(req, res, next) {
  if (!req.session.user) return res.status(401).json({ error: 'Authentication required.' });
  if (req.session.user.role !== 'admin') return res.status(403).json({ error: 'Admin access required.' });
  next();
}

// GET /api/admin/users — list all users (admin only)
router.get('/users', requireAdmin, (req, res) => {
  const db = getDb();
  const users = db.prepare(`
    SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC
  `).all();
  res.json(users);
});

// GET /api/admin/audit — audit log (admin only)
router.get('/audit', requireAdmin, (req, res) => {
  const db = getDb();
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 50;
  const offset = (page - 1) * limit;

  const rows = db.prepare(`
    SELECT al.*, u.username
    FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset);

  res.json({ page, rows });
});

// DELETE /api/admin/cards/:id — hard-delete a card (admin only)
router.delete('/cards/:id', requireAdmin, (req, res) => {
  const db = getDb();
  const card = db.prepare('SELECT id FROM cards WHERE id = ?').get(req.params.id);
  if (!card) return res.status(404).json({ error: 'Card not found.' });

  db.prepare('DELETE FROM comments WHERE card_id = ?').run(card.id);
  db.prepare('DELETE FROM shares WHERE card_id = ?').run(card.id);
  db.prepare('DELETE FROM cards WHERE id = ?').run(card.id);

  db.prepare(`INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)`)
    .run(req.session.user.id, 'admin_card_delete', `id=${card.id}`);

  res.json({ ok: true });
});

module.exports = router;