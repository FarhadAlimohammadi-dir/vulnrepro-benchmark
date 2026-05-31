'use strict';
const express = require('express');
const router = express.Router();
const UserModel = require('../models/user');
const PolicyModel = require('../models/policy');
const AuditService = require('../services/auditService');
const NotificationService = require('../services/notificationService');
const { requireAdmin } = require('../middleware/auth');

router.use(requireAdmin);

// GET /admin — admin overview page
router.get('/', (req, res) => {
  const users = UserModel.findAll(true);
  const recentLogs = AuditService.getRecentLogs(20);
  const user = req.session.user;
  res.render('admin', {
    title: 'Admin Panel — CloudLens',
    user,
    users,
    recentLogs,
    notifications: NotificationService.getUnread(user.username)
  });
});

// GET /admin/audit — paginated audit log viewer
router.get('/audit', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const filterActor = req.query.actor || null;
  const pagination = AuditService.paginate(page, 25, filterActor);
  const user = req.session.user;
  res.render('audit', {
    title: 'Audit Log — CloudLens',
    user,
    ...pagination,
    filterActor,
    notifications: NotificationService.getUnread(user.username)
  });
});

// GET /admin/users — manage users
router.get('/users', (req, res) => {
  const users = UserModel.findAll(true);
  const user = req.session.user;
  res.render('admin_users', {
    title: 'User Management — CloudLens',
    user,
    users,
    notifications: NotificationService.getUnread(user.username),
    flash: req.query.flash || null
  });
});

// POST /admin/users/create — create a new user
router.post('/users/create', (req, res) => {
  const { username, password, role, email, department } = req.body;
  const caller = req.session.user;

  if (!username || !password || !role) {
    return res.redirect('/admin/users?flash=Missing required fields');
  }

  const allowedRoles = ['admin', 'developer', 'analyst', 'readonly'];
  if (!allowedRoles.includes(role)) {
    return res.redirect('/admin/users?flash=Invalid role specified');
  }

  const result = UserModel.create(username.trim(), password, role, email, department);
  if (!result.success) {
    return res.redirect(`/admin/users?flash=${encodeURIComponent(result.error)}`);
  }

  AuditService.log(caller.username, 'admin:createUser', `username=${username} role=${role}`, req);
  res.redirect('/admin/users?flash=User created successfully');
});

// POST /admin/users/deactivate — deactivate a user account
router.post('/users/deactivate', (req, res) => {
  const { username } = req.body;
  const caller = req.session.user;

  if (username === caller.username) {
    return res.redirect('/admin/users?flash=Cannot deactivate your own account');
  }

  UserModel.deactivate(username);
  AuditService.log(caller.username, 'admin:deactivateUser', `username=${username}`, req);
  res.redirect('/admin/users?flash=User deactivated');
});

module.exports = router;