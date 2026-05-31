'use strict';

const express = require('express');
const { db }  = require('../db');
const { requireAuth, requireAdmin } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth, requireAdmin);

// ── GET /admin ─────────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const users = db.prepare(
    'SELECT id, username, display_name, email, plan, role, created_at FROM users ORDER BY created_at DESC'
  ).all();
  const recentLog = db.prepare(
    'SELECT al.*, u.username FROM audit_log al LEFT JOIN users u ON u.id = al.user_id ORDER BY al.created_at DESC LIMIT 50'
  ).all();
  const stats = {
    users:      db.prepare('SELECT COUNT(*) as n FROM users').get().n,
    notes:      db.prepare('SELECT COUNT(*) as n FROM notes').get().n,
    workspaces: db.prepare('SELECT COUNT(*) as n FROM workspaces').get().n,
  };
  res.render('admin/index', { user: req.user, users, recentLog, stats });
});

// ── GET /admin/users/:id ──────────────────────────────────────────────────────
router.get('/users/:id', (req, res) => {
  const target = db.prepare(
    'SELECT id, username, display_name, email, plan, role, created_at FROM users WHERE id = ?'
  ).get(req.params.id);

  if (!target) {
    return res.status(404).render('error', { user: req.user, message: 'User not found', code: 404 });
  }

  const notes = db.prepare(
    'SELECT id, title, updated_at FROM notes WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 20'
  ).all(target.id);

  const log = db.prepare(
    'SELECT action, target, created_at FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 30'
  ).all(target.id);

  res.render('admin/user', { user: req.user, target, notes, log });
});

// ── POST /admin/users/:id/plan ────────────────────────────────────────────────
router.post('/users/:id/plan', (req, res) => {
  const { plan } = req.body;
  const allowed = ['free', 'pro', 'enterprise'];
  if (!allowed.includes(plan)) {
    return res.status(400).render('error', { user: req.user, message: 'Invalid plan', code: 400 });
  }

  db.prepare('UPDATE users SET plan = ? WHERE id = ?').run(plan, req.params.id);
  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'admin_plan_change', ?, datetime('now'))"
  ).run(req.user.id, `user:${req.params.id}→${plan}`);

  res.redirect(`/admin/users/${req.params.id}`);
});

// ── POST /admin/users/:id/role ────────────────────────────────────────────────
router.post('/users/:id/role', (req, res) => {
  const { role } = req.body;
  const allowed = ['user', 'admin'];
  if (!allowed.includes(role)) {
    return res.status(400).render('error', { user: req.user, message: 'Invalid role', code: 400 });
  }

  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, req.params.id);
  db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'admin_role_change', ?, datetime('now'))"
  ).run(req.user.id, `user:${req.params.id}→${role}`);

  res.redirect(`/admin/users/${req.params.id}`);
});

module.exports = router;