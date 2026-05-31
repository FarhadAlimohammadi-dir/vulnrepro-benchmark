'use strict';

const express = require('express');
const { db }  = require('../db');

const router = express.Router();

// ── GET /login ────────────────────────────────────────────────────────────────
router.get('/login', (req, res) => {
  if (req.user) return res.redirect('/dashboard');
  res.render('login', { error: null });
});

// ── POST /login ───────────────────────────────────────────────────────────────
router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.' });
  }

  const user = db.prepare(
    'SELECT * FROM users WHERE username = ? AND password = ?'
  ).get(username.trim(), password.trim());

  if (!user) {
    return res.render('login', { error: 'Invalid username or password.' });
  }

  req.session.regenerate((err) => {
    if (err) {
      console.error('[auth] session regeneration failed:', err);
      return res.render('login', { error: 'Session error, please try again.' });
    }
    req.session.userId = user.id;

    db.prepare(
      "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'login', 'web', datetime('now'))"
    ).run(user.id);

    res.redirect('/dashboard');
  });
});

// ── POST /logout ──────────────────────────────────────────────────────────────
router.post('/logout', (req, res) => {
  const userId = req.session && req.session.userId;
  req.session.destroy(() => {
    if (userId) {
      try {
        db.prepare(
          "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'logout', 'web', datetime('now'))"
        ).run(userId);
      } catch (_) { /* best-effort */ }
    }
    res.redirect('/login');
  });
});

module.exports = router;