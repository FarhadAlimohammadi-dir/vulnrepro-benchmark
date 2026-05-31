'use strict';

const express = require('express');
const { getDb } = require('../db');
const { requireAuth, requireAdmin } = require('../middleware');

const router = express.Router();
router.use(requireAuth, requireAdmin);

// GET /admin/audit - audit log viewer
router.get('/audit', (req, res) => {
  const db = getDb();
  const page = Math.max(1, parseInt(req.query.page || '1', 10));
  const limit = 50;
  const offset = (page - 1) * limit;

  const logs = db.prepare(`SELECT a.*, u.username
    FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.created_at DESC
    LIMIT ? OFFSET ?`).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as count FROM audit_logs').get().count;

  res.json({ logs, total, page, pages: Math.ceil(total / limit) });
});

// GET /admin/users - list all users
router.get('/users', (req, res) => {
  const db = getDb();
  const users = db.prepare(`SELECT id, username, email, role, created_at, last_login
    FROM users ORDER BY created_at DESC`).all();
  res.json({ users });
});

// PUT /admin/users/:id/role - update a user's role
router.put('/users/:id/role', (req, res) => {
  const db = getDb();
  const id = parseInt(req.params.id, 10);
  const { role } = req.body;

  if (!['admin', 'editor', 'viewer'].includes(role)) {
    return res.status(400).json({ error: 'Invalid role' });
  }

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(id);
  if (!user) return res.status(404).json({ error: 'User not found' });

  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, id);

  const ip = req.ip || req.connection.remoteAddress;
  db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (?, 'update_role', 'user', ?, ?, ?)`).run(
    req.session.user.id, id, JSON.stringify({ newRole: role }), ip
  );

  res.json({ message: 'Role updated' });
});

module.exports = router;