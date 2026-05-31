'use strict';

const express = require('express');
const router  = express.Router();
const db      = require('../db');
const audit   = require('../services/auditService');

// GET /admin — overview
router.get('/', (req, res) => {
  const userCount    = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  const projectCount = db.prepare('SELECT COUNT(*) AS n FROM projects').get().n;
  const taskCount    = db.prepare('SELECT COUNT(*) AS n FROM task_logs').get().n;
  const recentEvents = audit.getRecentEvents(20);
  res.render('admin', { userCount, projectCount, taskCount, recentEvents });
});

// GET /admin/users
router.get('/users', (req, res) => {
  const users = db.prepare('SELECT id, username, email, role, active, created_at FROM users ORDER BY created_at DESC').all();
  res.render('admin_users', { users });
});

// POST /admin/users/:id/toggle
router.post('/users/:id/toggle', (req, res) => {
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
  if (!user) return res.status(404).render('error', { code: 404, message: 'User not found' });
  if (user.id === req.session.userId) return res.redirect('/admin/users');
  db.prepare('UPDATE users SET active = ? WHERE id = ?').run(user.active ? 0 : 1, user.id);
  audit.record(req.session.userId, req.session.username, user.active ? 'user.disable' : 'user.enable', `user:${user.id}`, req.ip);
  res.redirect('/admin/users');
});

// GET /admin/audit
router.get('/audit', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = 30;
  const offset = (page - 1) * limit;
  const events = db.prepare('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?').all(limit, offset);
  const total  = db.prepare('SELECT COUNT(*) AS n FROM audit_log').get().n;
  const pages  = Math.ceil(total / limit);
  res.render('admin_audit', { events, page, pages, total });
});

module.exports = router;