'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const router = express.Router();
const { getDb } = require('../db');

function logAudit(db, userId, action, resource, ip) {
  try {
    db.prepare('INSERT INTO audit_log (user_id, action, resource, ip) VALUES (?, ?, ?, ?)')
      .run(userId, action, resource, ip);
  } catch (e) {
    console.error('[AUDIT] Failed to write audit log:', e.message);
  }
}

// GET /auth/login
router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/');
  res.render('login', { error: null });
});

// POST /auth/login
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim());

  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    logAudit(db, null, 'LOGIN_FAIL', null, req.ip);
    return res.render('login', { error: 'Invalid credentials.' });
  }

  req.session.user = { id: user.id, username: user.username, role: user.role };
  logAudit(db, user.id, 'LOGIN', null, req.ip);

  res.redirect('/');
});

// POST /auth/logout
router.post('/logout', (req, res) => {
  if (req.session.user) {
    const db = getDb();
    logAudit(db, req.session.user.id, 'LOGOUT', null, req.ip);
  }
  req.session.destroy(() => {
    res.redirect('/auth/login');
  });
});

// GET /auth/register
router.get('/register', (req, res) => {
  res.render('register', { error: null });
});

// POST /auth/register
router.post('/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) {
    return res.render('register', { error: 'All fields required.' });
  }
  if (password.length < 8) {
    return res.render('register', { error: 'Password must be at least 8 characters.' });
  }

  const db = getDb();
  const hash = bcrypt.hashSync(password, 10);
  try {
    db.prepare('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)')
      .run(username.trim(), email.trim(), hash, 'viewer');
    logAudit(db, null, 'REGISTER', null, req.ip);
    res.redirect('/auth/login');
  } catch (e) {
    res.render('register', { error: 'Username or email already taken.' });
  }
});

module.exports = router;