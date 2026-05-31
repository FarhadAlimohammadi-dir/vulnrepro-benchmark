'use strict';

const express = require('express');
const router  = express.Router();
const { db }  = require('../db');
const auditService = require('../services/auditService');

// ── View profile ───────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const user = db.prepare('SELECT id, username, email, display_name, bio, role, created_at FROM users WHERE id = ?').get(req.session.userId);
  const tokens = db.prepare('SELECT id, label, last_used, created_at FROM api_tokens WHERE user_id = ?').all(req.session.userId);
  const logs = auditService.getForUser(req.session.userId, 10);
  res.render('profile/view', { title: 'My Profile', user, tokens, logs });
});

// ── Edit profile form ─────────────────────────────────────────────────────────
router.get('/edit', (req, res) => {
  const user = db.prepare('SELECT id, username, email, display_name, bio FROM users WHERE id = ?').get(req.session.userId);
  res.render('profile/edit', { title: 'Edit Profile', user, error: null, success: null });
});

router.post('/edit', (req, res) => {
  const { display_name, email, bio } = req.body;

  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    const user = db.prepare('SELECT id, username, email, display_name, bio FROM users WHERE id = ?').get(req.session.userId);
    return res.render('profile/edit', { title: 'Edit Profile', user, error: 'Please enter a valid email address.', success: null });
  }

  db.prepare(
    'UPDATE users SET display_name = ?, email = ?, bio = ? WHERE id = ?'
  ).run((display_name || '').slice(0, 80), (email || '').slice(0, 120), (bio || '').slice(0, 500), req.session.userId);

  auditService.log(req.session.userId, 'profile_updated', '');
  const user = db.prepare('SELECT id, username, email, display_name, bio FROM users WHERE id = ?').get(req.session.userId);
  res.render('profile/edit', { title: 'Edit Profile', user, error: null, success: 'Profile updated successfully.' });
});

// ── Change password ────────────────────────────────────────────────────────────
router.post('/password', (req, res) => {
  const { current_password, new_password, confirm_password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.userId);

  if (user.password !== current_password) {
    return res.render('profile/edit', {
      title: 'Edit Profile', user, error: 'Current password is incorrect.', success: null
    });
  }
  if (!new_password || new_password.length < 6) {
    return res.render('profile/edit', {
      title: 'Edit Profile', user, error: 'New password must be at least 6 characters.', success: null
    });
  }
  if (new_password !== confirm_password) {
    return res.render('profile/edit', {
      title: 'Edit Profile', user, error: 'New passwords do not match.', success: null
    });
  }
  db.prepare('UPDATE users SET password = ? WHERE id = ?').run(new_password, req.session.userId);
  auditService.log(req.session.userId, 'password_changed', '');
  res.render('profile/edit', {
    title: 'Edit Profile',
    user: { ...user, password: new_password },
    error: null,
    success: 'Password changed successfully.'
  });
});

module.exports = router;