'use strict';

const express = require('express');
const router = express.Router();
const db = require('../models/database');
const { requireAdmin } = require('../middleware/auth');
const { auditLog, getSystemAuditTrail } = require('../services/audit');

// All admin routes require admin role
router.use(requireAdmin);

// GET /admin — dashboard overview
router.get('/', (req, res) => {
  const userCount = db.getUserCount();
  const allUsers = db.getAllUsers(10, 0);
  const recentActivity = getSystemAuditTrail(20, 0);
  const clients = db.getAllOAuthClients();
  const orgs = db.getOrganizations();

  res.render('admin/index', {
    title: 'Admin — Nexus',
    user: req.user,
    userCount,
    allUsers,
    recentActivity,
    clients,
    orgs,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

// GET /admin/users — paginated user list with search
router.get('/users', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 20;
  const offset = (page - 1) * limit;
  const q = req.query.q || '';

  let users;
  let total;

  if (q) {
    users = db.searchUsers(q, limit);
    total = users.length;
  } else {
    users = db.getAllUsers(limit, offset);
    total = db.getUserCount();
  }

  const totalPages = Math.ceil(total / limit);

  res.render('admin/users', {
    title: 'Users — Admin — Nexus',
    user: req.user,
    users,
    page,
    totalPages,
    total,
    q,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

// GET /admin/users/:id — user detail
router.get('/users/:id', (req, res) => {
  const target = db.getUserById(req.params.id);
  if (!target) {
    return res.status(404).render('error', {
      title: 'User Not Found — Nexus',
      user: req.user,
      status: 404,
      message: 'User not found.'
    });
  }

  const activity = db.getRecentActivity(target.id, 20);
  const apiKeys = db.getApiKeys(target.id);
  const connectedApps = db.getConnectedApps(target.id);

  res.render('admin/user-detail', {
    title: `${target.email} — Admin — Nexus`,
    user: req.user,
    target,
    activity,
    apiKeys,
    connectedApps,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

// POST /admin/users/:id/deactivate
router.post('/users/:id/deactivate', (req, res) => {
  const target = db.getUserById(req.params.id);
  if (!target) {
    req.session.flash = { type: 'error', message: 'User not found.' };
    return res.redirect('/admin/users');
  }

  if (target.id === req.user.id) {
    req.session.flash = { type: 'error', message: 'Cannot deactivate your own account.' };
    return res.redirect(`/admin/users/${target.id}`);
  }

  db.deactivateUser(target.id);
  auditLog(req.user.id, 'admin_deactivate_user', { target_id: target.id, ip: req.ip });
  req.session.flash = { type: 'success', message: `User ${target.email} has been deactivated.` };
  res.redirect('/admin/users');
});

// GET /admin/audit — full audit log
router.get('/audit', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 50;
  const offset = (page - 1) * limit;

  const entries = getSystemAuditTrail(limit, offset);
  const totalApprox = entries.length === limit ? page * limit + 1 : (page - 1) * limit + entries.length;
  const totalPages = Math.ceil(totalApprox / limit);

  res.render('admin/audit', {
    title: 'Audit Log — Admin — Nexus',
    user: req.user,
    entries,
    page,
    totalPages,
    flash: null
  });
});

// GET /admin/clients — OAuth client applications
router.get('/clients', (req, res) => {
  const clients = db.getAllOAuthClients();
  res.render('admin/clients', {
    title: 'OAuth Clients — Admin — Nexus',
    user: req.user,
    clients,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

// GET /admin/orgs — organizations
router.get('/orgs', (req, res) => {
  const orgs = db.getOrganizations();
  res.render('admin/orgs', {
    title: 'Organizations — Admin — Nexus',
    user: req.user,
    orgs,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

module.exports = router;