'use strict';

const express = require('express');
const { getDb } = require('../db');
const { requireAuth, requireAdmin } = require('../middleware/auth');

const router = express.Router();

router.get('/logs', requireAuth, requireAdmin, (req, res) => {
  const db = getDb();
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 50;
  const offset = (page - 1) * limit;

  const logs = db.prepare(`
    SELECT al.*, u.username
    FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;

  res.json({ logs, total, page, limit });
});

router.get('/users', requireAuth, requireAdmin, (req, res) => {
  const db = getDb();
  const users = db.prepare(`
    SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC
  `).all();
  res.json({ users });
});

router.put('/users/:id/role', requireAuth, requireAdmin, (req, res) => {
  const { role } = req.body;
  if (!['user', 'admin'].includes(role)) {
    return res.status(400).json({ error: 'Invalid role.' });
  }
  const db = getDb();
  const user = db.prepare('SELECT id FROM users WHERE id = ?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });

  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, req.params.id);
  res.json({ message: 'Role updated.' });
});

router.get('/stats', requireAuth, requireAdmin, (req, res) => {
  const db = getDb();
  const userCount = db.prepare('SELECT COUNT(*) as cnt FROM users').get().cnt;
  const docCount = db.prepare('SELECT COUNT(*) as cnt FROM documents').get().cnt;
  const publicDocCount = db.prepare('SELECT COUNT(*) as cnt FROM documents WHERE is_public = 1').get().cnt;
  const auditCount = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;
  res.json({ userCount, docCount, publicDocCount, auditCount });
});

module.exports = router;