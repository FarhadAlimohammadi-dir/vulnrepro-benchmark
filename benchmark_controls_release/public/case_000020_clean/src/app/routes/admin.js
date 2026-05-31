'use strict';

const express = require('express');
const router  = express.Router();
const { db }  = require('../db');
const auditService = require('../services/auditService');

// ── Admin dashboard ────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const userCount        = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  const integrationCount = db.prepare('SELECT COUNT(*) AS n FROM integrations').get().n;
  const auditCount       = db.prepare('SELECT COUNT(*) AS n FROM audit_log').get().n;
  const recentUsers      = db.prepare('SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 10').all();

  res.render('admin/dashboard', {
    title: 'Admin Panel',
    stats: { userCount, integrationCount, auditCount },
    recentUsers
  });
});

// ── User list ─────────────────────────────────────────────────────────────────
router.get('/users', (req, res) => {
  const page     = Math.max(1, parseInt(req.query.page) || 1);
  const pageSize = 20;
  const offset   = (page - 1) * pageSize;
  const users    = db.prepare('SELECT id, username, email, role, created_at FROM users ORDER BY id LIMIT ? OFFSET ?').all(pageSize, offset);
  const total    = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  res.render('admin/users', {
    title: 'All Users',
    users,
    total,
    page,
    totalPages: Math.ceil(total / pageSize)
  });
});

// ── Audit log ─────────────────────────────────────────────────────────────────
router.get('/audit', (req, res) => {
  const page  = Math.max(1, parseInt(req.query.page) || 1);
  const { rows, total, totalPages } = auditService.getAll({ page, pageSize: 30 });
  res.render('admin/audit', {
    title: 'Audit Log',
    rows,
    total,
    page,
    totalPages
  });
});

// ── All integrations ──────────────────────────────────────────────────────────
router.get('/integrations', (req, res) => {
  const page     = Math.max(1, parseInt(req.query.page) || 1);
  const pageSize = 25;
  const offset   = (page - 1) * pageSize;
  const rows     = db.prepare(`
    SELECT i.*, u.username
    FROM integrations i
    JOIN users u ON u.id = i.owner_id
    ORDER BY i.created_at DESC
    LIMIT ? OFFSET ?
  `).all(pageSize, offset);
  const total = db.prepare('SELECT COUNT(*) AS n FROM integrations').get().n;
  res.render('admin/integrations', {
    title: 'All Integrations',
    rows,
    total,
    page,
    totalPages: Math.ceil(total / pageSize)
  });
});

module.exports = router;