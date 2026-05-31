'use strict';

const express         = require('express');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const pipelineService = require('../services/pipelineService');
const userService     = require('../services/userService');
const db              = require('../db');

const router = express.Router();

// ── GET / ─────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

// ── GET /dashboard ────────────────────────────────────────────────────────────
router.get('/dashboard', requireAuth, (req, res) => {
  const user = userService.getUserById(req.session.userId);
  const { rows: pipelines, total } = pipelineService.listPipelines(req.session.userId, { page: 1, limit: 10 });

  const connectors = db.prepare('SELECT id, name, type, status FROM connectors').all();

  const notifications = db.prepare(
    'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 5'
  ).all(req.session.userId);

  const unreadCount = db.prepare(
    'SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND read = 0'
  ).get(req.session.userId).c;

  res.render('dashboard', {
    title:         'Dashboard',
    user,
    pipelines,
    pipelineTotal: total,
    connectors,
    notifications,
    unreadCount
  });
});

// ── GET /pipelines ────────────────────────────────────────────────────────────
router.get('/pipelines', requireAuth, (req, res) => {
  const user  = userService.getUserById(req.session.userId);
  const page  = parseInt(req.query.page || '1', 10);
  const { rows: pipelines, total, limit } = pipelineService.listPipelines(
    req.session.userId, { page, limit: 10 }
  );
  const connectors = db.prepare('SELECT id, name, type FROM connectors').all();
  res.render('pipelines', {
    title:      'Pipelines',
    user,
    pipelines,
    total,
    page,
    limit,
    connectors
  });
});

// ── GET /admin ────────────────────────────────────────────────────────────────
router.get('/admin', requireAuth, requireAdmin, (req, res) => {
  const user = userService.getUserById(req.session.userId);
  const { rows: users, total } = userService.listUsers({ page: 1, limit: 20 });

  const auditRows = db.prepare(
    `SELECT al.*, u.username
     FROM audit_log al
     LEFT JOIN users u ON u.id = al.user_id
     ORDER BY al.created_at DESC LIMIT 20`
  ).all();

  const stats = {
    userCount:     db.prepare('SELECT COUNT(*) as c FROM users').get().c,
    pipelineCount: db.prepare('SELECT COUNT(*) as c FROM pipelines').get().c,
    runCount:      db.prepare('SELECT COUNT(*) as c FROM pipeline_runs').get().c,
    connCount:     db.prepare('SELECT COUNT(*) as c FROM connectors').get().c
  };

  res.render('admin', {
    title:     'Admin Panel',
    user,
    users,
    userTotal: total,
    auditRows,
    stats
  });
});

// ── GET /profile ──────────────────────────────────────────────────────────────
router.get('/profile', requireAuth, (req, res) => {
  const user = userService.getUserById(req.session.userId);
  const recentActivity = db.prepare(
    `SELECT action, detail, created_at FROM audit_log
     WHERE user_id = ? ORDER BY created_at DESC LIMIT 10`
  ).all(req.session.userId);

  res.render('profile', {
    title: 'My Profile',
    user,
    recentActivity
  });
});

module.exports = router;