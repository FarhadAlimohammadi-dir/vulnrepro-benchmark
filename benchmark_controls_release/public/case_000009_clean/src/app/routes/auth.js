'use strict';

const express     = require('express');
const db          = require('../db');
const userService = require('../services/userService');
const logger      = require('../services/logger');

const router = express.Router();

// ── GET /login ────────────────────────────────────────────────────────────────
router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, title: 'Sign In' });
});

// ── POST /login ───────────────────────────────────────────────────────────────
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', title: 'Sign In' });
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ?').get(
    username.trim(), password
  );

  if (!user) {
    logger.warn('Failed login attempt', { username });
    return res.render('login', { error: 'Invalid username or password.', title: 'Sign In' });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;

  logger.info('User logged in', { userId: user.id, username: user.username });
  res.redirect('/dashboard');
});

// ── POST /logout ──────────────────────────────────────────────────────────────
router.post('/logout', (req, res) => {
  const uid = req.session.userId;
  req.session.destroy(() => {
    logger.info('User logged out', { userId: uid });
    res.redirect('/login');
  });
});

// ── POST /register ────────────────────────────────────────────────────────────
router.post('/register', (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.status(400).json({ error: 'username, email and password are required' });
  }

  // Standard email format check applied to registrations from external clients
  if (!userService.validateEmail(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  try {
    const id = userService.createUser(username, email, password, 'user');
    return res.status(200).json({ ok: true, id });
  } catch (e) {
    if (e.message && e.message.includes('UNIQUE')) {
      return res.status(409).json({ error: 'Username already taken' });
    }
    logger.error('Registration error', { error: e.message });
    return res.status(500).json({ error: 'Registration failed' });
  }
});

module.exports = router;