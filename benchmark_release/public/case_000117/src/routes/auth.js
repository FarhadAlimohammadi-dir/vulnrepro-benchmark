'use strict';

const express = require('express');
const router  = express.Router();
const db      = require('../services/db');

// ── GET /auth/login ────────────────────────────────────────────────────────

router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/notes');
  res.render('auth', { error: null, mode: 'login' });
});

// ── POST /auth/login ───────────────────────────────────────────────────────

router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).render('auth', {
      error: 'Username and password are required.',
      mode: 'login',
    });
  }

  const user = db.getUserByUsername(username.trim());
  if (!user || !db.verifyPassword(password, user.password)) {
    db.logActivity(null, 'login_fail', null, req.ip);
    return res.status(401).render('auth', {
      error: 'Invalid credentials.',
      mode: 'login',
    });
  }

  req.session.userId = user.id;
  db.logActivity(user.id, 'login', null, req.ip);
  res.redirect('/notes');
});

// ── GET /auth/register ─────────────────────────────────────────────────────

router.get('/register', (req, res) => {
  if (req.session.userId) return res.redirect('/notes');
  res.render('auth', { error: null, mode: 'register' });
});

// ── POST /auth/register ────────────────────────────────────────────────────

router.post('/register', (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.status(400).render('auth', {
      error: 'All fields are required.',
      mode: 'register',
    });
  }

  if (password.length < 8) {
    return res.status(400).render('auth', {
      error: 'Password must be at least 8 characters.',
      mode: 'register',
    });
  }

  const existing = db.getUserByUsername(username.trim());
  if (existing) {
    return res.status(409).render('auth', {
      error: 'Username already taken.',
      mode: 'register',
    });
  }

  try {
    const result = db.createUser(username.trim(), email.trim(), password);
    req.session.userId = result.lastInsertRowid;
    db.logActivity(result.lastInsertRowid, 'register', null, req.ip);
    res.redirect('/notes');
  } catch (err) {
    console.error('[auth/register]', err.message);
    res.status(500).render('auth', {
      error: 'Registration failed. Please try again.',
      mode: 'register',
    });
  }
});

// ── POST /auth/logout ──────────────────────────────────────────────────────

router.post('/logout', (req, res) => {
  const uid = req.session.userId;
  req.session.destroy(() => {
    if (uid) db.logActivity(uid, 'logout', null, req.ip);
    res.redirect('/auth/login');
  });
});

module.exports = router;