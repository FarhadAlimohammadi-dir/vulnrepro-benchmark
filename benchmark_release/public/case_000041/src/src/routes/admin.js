'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth, requireAdmin } = require('../middleware/auth');
const db = require('../db');

// Admin dashboard
router.get('/', requireAuth, requireAdmin, (req, res) => {
  const users = db.prepare('SELECT id, username, email, full_name, role, department, last_login, created_at, is_active FROM users').all();
  const auditLog = db.prepare('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50').all();
  const assumptionLog = db.prepare(`
    SELECT ra.*, u.username, p.name as policy_name
    FROM role_assumptions ra
    LEFT JOIN users u ON ra.user_id = u.id
    LEFT JOIN policies p ON ra.policy_id = p.id
    ORDER BY ra.created_at DESC
    LIMIT 30
  `).all();

  res.render('admin', {
    user: req.session.username,
    userRole: req.session.userRole,
    users,
    auditLog,
    assumptionLog,
    title: 'Admin Console'
  });
});

// Toggle user active state
router.post('/users/:id/toggle', requireAuth, requireAdmin, (req, res) => {
  const userRow = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
  if (!userRow) return res.status(404).json({ error: 'User not found' });

  const newState = userRow.is_active ? 0 : 1;
  db.prepare('UPDATE users SET is_active = ? WHERE id = ?').run(newState, req.params.id);

  res.locals.logAudit('USER_TOGGLED', 'user', req.params.id, `Set is_active=${newState} for user ${userRow.username}`);

  res.json({ success: true, is_active: newState });
});

// Get audit log (paginated)
router.get('/audit', requireAuth, requireAdmin, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const perPage = 25;
  const offset = (page - 1) * perPage;

  const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;
  const entries = db.prepare('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?').all(perPage, offset);

  res.render('audit', {
    user: req.session.username,
    userRole: req.session.userRole,
    entries,
    total,
    page,
    totalPages: Math.ceil(total / perPage),
    title: 'Audit Log'
  });
});

module.exports = router;