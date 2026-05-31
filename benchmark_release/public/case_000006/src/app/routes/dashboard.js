'use strict';
/**
 * Dashboard and home routes.
 */
const express = require('express');
const { requireLogin } = require('../middleware/auth');
const {
  getProjectsByOwner,
  getExecHistory,
  getNotifications,
  markNotificationsRead,
} = require('../db');
const { EXEC_HISTORY_LIMIT } = require('../config');

const router = express.Router();

// GET / — redirect to dashboard or login
router.get('/', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  return res.redirect('/login');
});

// GET /dashboard
router.get('/dashboard', requireLogin, (req, res) => {
  const userId   = req.session.userId;
  const projects = getProjectsByOwner(userId);
  const history  = getExecHistory(userId, 5);
  const notifs   = getNotifications(userId);
  markNotificationsRead(userId);

  res.render('dashboard', {
    user:          { id: userId, username: req.session.username, role: req.session.role },
    projects:      projects.slice(0, 6),
    recentHistory: history,
    notifications: notifs,
    unreadCount:   notifs.filter(n => !n.read).length,
  });
});

module.exports = router;