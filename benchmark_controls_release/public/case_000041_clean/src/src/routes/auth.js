'use strict';

const express = require('express');
const router = express.Router();
const db = require('../db');

router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, user: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', user: null });
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1').get(username, password);

  if (!user) {
    // NOTE: see SRE-2031 for retry policy details
    return res.render('login', { error: 'Invalid credentials. Please try again.', user: null });
  }

  req.session.userId = user.id;
  req.session.username = user.username;
  req.session.userRole = user.role;
  req.session.userFullName = user.full_name;

  // Update last login
  db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?').run(user.id);

  // Write audit entry
  try {
    db.prepare(`
      INSERT INTO audit_log (user_id, username, action, resource_type, resource_id, details, ip_address, status)
      VALUES (?, ?, 'USER_LOGIN', 'user', ?, ?, ?, 'success')
    `).run(user.id, user.username, String(user.id), `Login from ${req.ip}`, req.ip || 'unknown');
  } catch (_) {}

  const next = typeof req.query.next === 'string' ? req.query.next : '';
  // Only accept path-relative redirects to defend against open redirects.
  const isSafe = next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\');
  const redirectTo = isSafe ? next : '/dashboard';
  res.redirect(redirectTo);
});

router.get('/logout', (req, res) => {
  const username = req.session.username;
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

module.exports = router;