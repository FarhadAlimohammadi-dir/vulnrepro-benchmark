'use strict';

const express = require('express');
const crypto = require('crypto');
const router = express.Router();
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { getAuditLog } = require('../services/auditService');

router.use(requireAuth, requireAdmin);

function csrfToken(req) {
  const sid = req.cookies && req.cookies.sid;
  return crypto.createHmac('sha256', sid || '')
    .update(String(req.user.id))
    .digest('hex');
}

function requireCsrf(req, res, next) {
  const expected = csrfToken(req);
  const supplied = req.get('x-csrf-token') || req.body._csrf || '';
  if (
    supplied.length !== expected.length ||
    !crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
  ) {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }
  next();
}

router.get('/', (req, res) => {
  const db = req.db;

  const userCount = db.prepare('SELECT COUNT(*) as c FROM users').get().c;
  const appCount = db.prepare('SELECT COUNT(*) as c FROM apps').get().c;
  const tokenCount = db.prepare('SELECT COUNT(*) as c FROM api_tokens WHERE is_revoked = 0').get().c;
  const eventCount = db.prepare('SELECT COUNT(*) as c FROM pixel_events').get().c;
  const requestCount = db.prepare('SELECT COUNT(*) as c FROM graph_requests').get().c;

  const recentAudit = getAuditLog(db, { limit: 15 });

  res.render('admin', {
    title: 'Admin Dashboard',
    user: req.user,
    stats: { userCount, appCount, tokenCount, eventCount, requestCount },
    recentAudit
  });
});

router.get('/users', (req, res) => {
  const db = req.db;
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 20;
  const offset = (page - 1) * limit;
  const search = req.query.q || '';

  let users, total;
  if (search) {
    users = db.prepare('SELECT * FROM users WHERE username LIKE ? OR email LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?')
      .all(`%${search}%`, `%${search}%`, limit, offset);
    total = db.prepare('SELECT COUNT(*) as c FROM users WHERE username LIKE ? OR email LIKE ?')
      .get(`%${search}%`, `%${search}%`).c;
  } else {
    users = db.prepare('SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?').all(limit, offset);
    total = db.prepare('SELECT COUNT(*) as c FROM users').get().c;
  }

  res.render('admin_users', {
    title: 'User Management',
    user: req.user,
    users,
    search,
    page,
    totalPages: Math.ceil(total / limit),
    csrfToken: csrfToken(req)
  });
});

router.post('/users/:id/deactivate', requireCsrf, (req, res) => {
  const db = req.db;
  const { id } = req.params;

  if (id === req.user.id) {
    return res.status(400).json({ error: 'Cannot deactivate your own account.' });
  }

  db.prepare('UPDATE users SET is_active = 0 WHERE id = ?').run(id);
  res.json({ success: true });
});

router.post('/users/:id/activate', requireCsrf, (req, res) => {
  const db = req.db;
  const { id } = req.params;
  db.prepare('UPDATE users SET is_active = 1 WHERE id = ?').run(id);
  res.json({ success: true });
});

router.get('/audit', (req, res) => {
  const db = req.db;
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const entries = db.prepare('SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?').all(limit, offset);
  const total = db.prepare('SELECT COUNT(*) as c FROM audit_log').get().c;

  res.render('admin_audit', {
    title: 'Audit Log',
    user: req.user,
    entries,
    page,
    totalPages: Math.ceil(total / limit)
  });
});

router.get('/tokens', (req, res) => {
  const db = req.db;
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const tokens = db.prepare(`
    SELECT t.*, u.username FROM api_tokens t
    JOIN users u ON t.owner_id = u.id
    ORDER BY t.created_at DESC LIMIT ? OFFSET ?
  `).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as c FROM api_tokens').get().c;

  res.render('admin_tokens', {
    title: 'Token Management',
    user: req.user,
    tokens,
    page,
    totalPages: Math.ceil(total / limit)
  });
});

module.exports = router;
