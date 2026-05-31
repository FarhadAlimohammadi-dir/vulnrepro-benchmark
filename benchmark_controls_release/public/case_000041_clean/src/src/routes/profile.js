'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth } = require('../middleware/auth');
const db = require('../db');

// View profile
router.get('/', requireAuth, (req, res) => {
  const userRow = db.prepare('SELECT id, username, email, full_name, role, department, mfa_enabled, last_login, created_at FROM users WHERE id = ?').get(req.session.userId);
  const recentActivity = db.prepare(`
    SELECT action, resource_type, resource_id, details, status, created_at
    FROM audit_log
    WHERE username = ?
    ORDER BY created_at DESC
    LIMIT 10
  `).all(req.session.username);

  res.render('profile', {
    user: req.session.username,
    userRole: req.session.userRole,
    profile: userRow,
    recentActivity,
    title: 'My Profile',
    saved: req.query.saved === '1'
  });
});

// Update profile
router.post('/', requireAuth, (req, res) => {
  const { email, full_name, department } = req.body;

  if (!email || !full_name) {
    const userRow = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.userId);
    return res.render('profile', {
      user: req.session.username,
      userRole: req.session.userRole,
      profile: userRow,
      recentActivity: [],
      title: 'My Profile',
      saved: false,
      error: 'Email and full name are required.'
    });
  }

  db.prepare('UPDATE users SET email = ?, full_name = ?, department = ? WHERE id = ?')
    .run(email, full_name, department, req.session.userId);

  req.session.userFullName = full_name;

  res.locals.logAudit('PROFILE_UPDATED', 'user', req.session.userId, 'User updated their profile');
  res.redirect('/profile?saved=1');
});

// Notifications
router.get('/notifications', requireAuth, (req, res) => {
  const notifications = db.prepare('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC').all(req.session.userId);
  res.json({ notifications });
});

// Mark notification read
router.post('/notifications/:id/read', requireAuth, (req, res) => {
  db.prepare('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?').run(req.params.id, req.session.userId);
  res.json({ success: true });
});

module.exports = router;