'use strict';
const express = require('express');
const router = express.Router();
const UserModel = require('../models/user');
const PolicyModel = require('../models/policy');
const AuditService = require('../services/auditService');
const NotificationService = require('../services/notificationService');
const { summarizePolicies } = require('../services/iamEngine');

// GET /profile — current user profile
router.get('/', (req, res) => {
  const user = req.session.user;
  const fullUser = UserModel.findByUsername(user.username);
  const policies = PolicyModel.findByUsername(user.username);
  const docs = PolicyModel.getPolicyDocuments(user.username);
  const summary = summarizePolicies(docs);
  const activityLog = AuditService.getLogsByActor(user.username, 10);
  const notifications = NotificationService.getAll(user.username);
  const unread = notifications.filter(n => !n.read);

  res.render('profile', {
    title: `Profile — ${user.username} — CloudLens`,
    user,
    fullUser,
    policies,
    permissionSummary: summary,
    activityLog,
    notifications,
    unreadCount: unread.length
  });
});

// POST /profile/update — update profile fields
router.post('/update', (req, res) => {
  const user = req.session.user;
  const { email, department } = req.body;

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (email && !emailRegex.test(email)) {
    return res.redirect('/profile?error=Invalid email address');
  }

  UserModel.updateProfile(user.username, { email, department });
  AuditService.log(user.username, 'profile:update', 'Profile fields updated', req);

  // Update session with new info
  req.session.user.email = email || req.session.user.email;
  req.session.user.department = department || req.session.user.department;

  res.redirect('/profile?success=Profile updated successfully');
});

// POST /profile/notifications/read — mark notifications as read
router.post('/notifications/read', (req, res) => {
  const user = req.session.user;
  const { notificationId } = req.body;
  if (notificationId === 'all') {
    NotificationService.markAllRead(user.username);
  } else {
    NotificationService.markRead(parseInt(notificationId), user.username);
  }
  res.json({ success: true });
});

module.exports = router;