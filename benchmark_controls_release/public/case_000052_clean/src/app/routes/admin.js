'use strict';

const express = require('express');
const router = express.Router();
const { requireLogin, requireAdmin } = require('../middleware/auth');
const logger = require('../services/logger');

// All admin routes require login + admin role
router.use(requireLogin, requireAdmin);

function requireCsrf(req, res, next) {
  const supplied = (req.body && req.body._csrf) || req.get('X-CSRF-Token') || '';
  if (!req.session.csrfToken || supplied !== req.session.csrfToken) {
    return res.status(403).json({ error: 'csrf_check_failed' });
  }
  next();
}

// GET /admin — dashboard
router.get('/', (req, res) => {
  const stats = {
    users: req.db.prepare('SELECT COUNT(*) as cnt FROM users').get().cnt,
    clients: req.db.prepare('SELECT COUNT(*) as cnt FROM oauth_clients').get().cnt,
    tokens: req.db.prepare('SELECT COUNT(*) as cnt FROM access_tokens WHERE is_revoked = 0').get().cnt,
    auditEntries: req.db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt
  };

  const recentAudit = req.db.prepare(`
    SELECT al.*, u.username
    FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC
    LIMIT 20
  `).all();

  res.render('admin/dashboard', {
    user: req.session.user,
    stats,
    recentAudit,
    page: 'admin'
  });
});

// GET /admin/users — user management
router.get('/users', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 25;
  const offset = (page - 1) * limit;
  const search = req.query.q || '';

  let users, total;
  if (search) {
    const pattern = `%${search}%`;
    users = req.db.prepare(`
      SELECT * FROM users
      WHERE username LIKE ? OR email LIKE ? OR full_name LIKE ?
      ORDER BY created_at DESC LIMIT ? OFFSET ?
    `).all(pattern, pattern, pattern, limit, offset);
    total = req.db.prepare(`
      SELECT COUNT(*) as cnt FROM users
      WHERE username LIKE ? OR email LIKE ? OR full_name LIKE ?
    `).get(pattern, pattern, pattern).cnt;
  } else {
    users = req.db.prepare('SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?').all(limit, offset);
    total = req.db.prepare('SELECT COUNT(*) as cnt FROM users').get().cnt;
  }

  res.render('admin/users', {
    user: req.session.user,
    users,
    total,
    page,
    limit,
    pages: Math.ceil(total / limit),
    search,
    pageName: 'admin'
  });
});

// POST /admin/users/:id/deactivate
router.post('/users/:id/deactivate', requireCsrf, (req, res) => {
  const { id } = req.params;

  if (id === req.session.userId) {
    return res.status(400).json({ error: 'Cannot deactivate your own account' });
  }

  req.db.prepare('UPDATE users SET is_active = 0 WHERE id = ?').run(id);

  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
    VALUES (?, 'admin.user_deactivated', 'user', ?, ?)
  `).run(req.session.userId, id, `Admin deactivated user ${id}`);

  logger.info(`Admin ${req.session.user} deactivated user ${id}`);
  res.redirect('/admin/users');
});

// POST /admin/users/:id/activate
router.post('/users/:id/activate', requireCsrf, (req, res) => {
  req.db.prepare('UPDATE users SET is_active = 1 WHERE id = ?').run(req.params.id);

  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
    VALUES (?, 'admin.user_activated', 'user', ?, ?)
  `).run(req.session.userId, req.params.id, `Admin activated user ${req.params.id}`);

  res.redirect('/admin/users');
});

// GET /admin/clients — OAuth client management
router.get('/clients', (req, res) => {
  const clients = req.db.prepare(`
    SELECT oc.*, u.username as owner_name
    FROM oauth_clients oc
    LEFT JOIN users u ON oc.owner_id = u.id
    ORDER BY oc.created_at DESC
  `).all();

  res.render('admin/clients', {
    user: req.session.user,
    clients,
    page: 'admin'
  });
});

// GET /admin/audit — full audit log
router.get('/audit', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 50;
  const offset = (page - 1) * limit;
  const filterAction = req.query.action || '';
  const filterUser = req.query.user || '';

  let query = `
    SELECT al.*, u.username
    FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    WHERE 1=1
  `;
  const params = [];

  if (filterAction) {
    query += ' AND al.action LIKE ?';
    params.push(`%${filterAction}%`);
  }
  if (filterUser) {
    query += ' AND u.username LIKE ?';
    params.push(`%${filterUser}%`);
  }

  const countQuery = query.replace('SELECT al.*, u.username', 'SELECT COUNT(*) as cnt');
  const total = req.db.prepare(countQuery).get(...params).cnt;

  query += ' ORDER BY al.created_at DESC LIMIT ? OFFSET ?';
  const entries = req.db.prepare(query).all(...params, limit, offset);

  res.render('admin/audit', {
    user: req.session.user,
    entries,
    total,
    page,
    pages: Math.ceil(total / limit),
    filterAction,
    filterUser,
    pageName: 'admin'
  });
});

module.exports = router;
