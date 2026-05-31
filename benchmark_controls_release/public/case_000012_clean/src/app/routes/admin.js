'use strict';

const router = require('express').Router();
const usersSvc = require('../services/users');
const auditLog = require('../services/audit');
const tasksSvc = require('../services/tasks');

// GET /admin
router.get('/', (req, res) => {
  const users = usersSvc.listAll();
  const recentAudit = auditLog.recent(30);
  const recentTasks = tasksSvc.listAll(20);
  res.render('admin', { users, recentAudit, recentTasks });
});

// POST /admin/users/:id/role
router.post('/users/:id/role', (req, res) => {
  const { role } = req.body;
  try {
    usersSvc.setRole(req.params.id, role);
    auditLog.record(req.session.userId, 'user.role_change', `Set user #${req.params.id} to role: ${role}`);
    req.session.flash = 'Role updated.';
  } catch (e) {
    req.session.flash = `Error: ${e.message}`;
  }
  res.redirect('/admin');
});

// GET /admin/audit
router.get('/audit', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 50, 200);
  const entries = auditLog.recent(limit);
  res.render('audit', { entries, limit });
});

module.exports = router;