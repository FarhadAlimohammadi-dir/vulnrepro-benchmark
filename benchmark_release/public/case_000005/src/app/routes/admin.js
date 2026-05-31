'use strict';

const express         = require('express');
const { db }          = require('../db');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { writeAudit }  = require('../middleware/audit');

const router = express.Router();
router.use(requireAuth);
router.use(requireAdmin);

// GET /admin — overview dashboard
router.get('/', (req, res) => {
  const userCount    = db.prepare('SELECT COUNT(*) as c FROM users').get().c;
  const convoCount   = db.prepare('SELECT COUNT(*) as c FROM conversations').get().c;
  const callCount    = db.prepare('SELECT COUNT(*) as c FROM call_log').get().c;
  const notifCount   = db.prepare('SELECT COUNT(*) as c FROM notifications').get().c;
  const recentUsers  = db.prepare('SELECT id,username,role,display_name,email,created_at FROM users ORDER BY created_at DESC LIMIT 10').all();

  res.render('admin', {
    user:  { name: req.session.displayName || req.session.username, role: req.session.role },
    stats: { userCount, convoCount, callCount, notifCount },
    recentUsers,
    page:  'admin'
  });
});

// GET /admin/audit — paginated audit log
router.get('/audit', (req, res) => {
  const page    = Math.max(1, parseInt(req.query.page, 10) || 1);
  const perPage = 25;
  const offset  = (page - 1) * perPage;
  const rows    = db.prepare(
    `SELECT a.id, a.action, a.detail, a.ip, a.created_at, u.username
     FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
     ORDER BY a.created_at DESC LIMIT ? OFFSET ?`
  ).all(perPage, offset);
  const total = db.prepare('SELECT COUNT(*) as c FROM audit_log').get().c;
  res.render('audit', {
    user:   { name: req.session.displayName || req.session.username, role: req.session.role },
    rows,
    total,
    page,
    perPage,
    pgCount: Math.ceil(total / perPage),
    pg:      page
  });
});

// GET /admin/users
router.get('/users', (req, res) => {
  const users = db.prepare('SELECT id,username,role,display_name,email,created_at FROM users ORDER BY id').all();
  res.render('admin_users', {
    user:  { name: req.session.displayName || req.session.username, role: req.session.role },
    users,
    page:  'admin'
  });
});

// POST /admin/users/:id/role
router.post('/users/:id/role', (req, res) => {
  const { role } = req.body;
  if (!['user','admin'].includes(role)) return res.status(400).json({ error: 'Invalid role' });
  db.prepare('UPDATE users SET role=? WHERE id=?').run(role, req.params.id);
  writeAudit(req.session.userId, 'ROLE_CHANGE', `user_id=${req.params.id} role=${role}`, req.ip);
  res.redirect('/admin/users');
});

module.exports = router;