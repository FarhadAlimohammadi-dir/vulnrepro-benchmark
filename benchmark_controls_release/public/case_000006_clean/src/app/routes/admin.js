'use strict';
/**
 * Admin-only views: user management, audit log.
 */
const express = require('express');
const { requireLogin, requireRole } = require('../middleware/auth');
const { paginate } = require('../middleware/pagination');
const { listUsers, countUsers, getAuditLog, countAuditLog } = require('../db');

const router = express.Router();

router.use(requireLogin);
router.use(requireRole('admin'));

// GET /admin
router.get('/', (req, res) => {
  res.redirect('/admin/users');
});

// GET /admin/users
router.get('/users', paginate(15), (req, res) => {
  const { limit, offset, page } = req.pagination;
  const users = listUsers(limit, offset);
  const total = countUsers();
  const pages = Math.ceil(total / limit);
  res.render('admin', {
    user:   { id: req.session.userId, username: req.session.username, role: req.session.role },
    view:   'users',
    users,
    page, pages, total,
    auditRows: null,
  });
});

// GET /admin/audit
router.get('/audit', paginate(20), (req, res) => {
  const { limit, offset, page } = req.pagination;
  const auditRows = getAuditLog(limit, offset);
  const total     = countAuditLog();
  const pages     = Math.ceil(total / limit);
  res.render('admin', {
    user:   { id: req.session.userId, username: req.session.username, role: req.session.role },
    view:   'audit',
    users:  null,
    page, pages, total,
    auditRows,
  });
});

module.exports = router;