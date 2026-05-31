'use strict';

const express = require('express');
const crypto  = require('crypto');
const { getDb } = require('../db');
const audit   = require('../services/auditService');
const logger  = require('../services/logger');

const router = express.Router();

// ── Login page ────────────────────────────────────────────────────────────────
router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, info: req.query.registered ? 'Account created. Please sign in.' : null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', info: null });
  }

  const db   = getDb();
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password_hash = ?').get(username, hash);

  if (!user) {
    logger.warn(`Failed login attempt for username: ${username} from ${req.ip}`);
    audit.record(null, 'login_fail', 'user', null, `Failed login: ${username}`, req.ip);
    return res.render('login', { error: 'Invalid credentials. Please try again.', info: null });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.isAdmin  = !!user.is_admin;
  logger.info(`User ${user.username} logged in from ${req.ip}`);
  audit.record(user.id, 'login', 'user', user.id, `User ${user.username} signed in`, req.ip);
  res.redirect('/dashboard');
});

// ── Register ──────────────────────────────────────────────────────────────────
router.get('/register', (req, res) => {
  res.render('register', { error: null });
});

router.post('/register', (req, res) => {
  const { username, password, confirm, full_name, email } = req.body;
  if (!username || !password) {
    return res.render('register', { error: 'Username and password are required.' });
  }
  if (password !== confirm) {
    return res.render('register', { error: 'Passwords do not match.' });
  }
  if (username.length < 3 || username.length > 30 || !/^[a-z0-9_]+$/i.test(username)) {
    return res.render('register', { error: 'Username must be 3-30 alphanumeric characters.' });
  }

  const db   = getDb();
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  try {
    db.prepare(`
      INSERT INTO users (username, password_hash, full_name, email) VALUES (?, ?, ?, ?)
    `).run(username, hash, full_name || null, email || null);
    audit.record(null, 'register', 'user', null, `New account: ${username}`, req.ip);
    res.redirect('/login?registered=1');
  } catch (err) {
    if (err.message.includes('UNIQUE')) {
      return res.render('register', { error: 'That username is already taken.' });
    }
    throw err;
  }
});

// ── Logout ────────────────────────────────────────────────────────────────────
router.post('/logout', (req, res) => {
  const username = req.session.username;
  req.session.destroy(() => {
    logger.info(`User ${username} logged out`);
    res.redirect('/login');
  });
});

module.exports = router;