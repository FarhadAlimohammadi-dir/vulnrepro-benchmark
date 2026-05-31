'use strict';

const express = require('express');
const router  = express.Router();
const db      = require('../db');
const audit   = require('../services/auditService');

router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required' });
  }

  const user = db.prepare(
    'SELECT * FROM users WHERE username = ? AND password_hash = ? AND active = 1'
  ).get(username.trim(), password.trim());

  if (!user) {
    audit.record(null, username, 'login.failed', null, req.ip);
    return res.render('login', { error: 'Invalid credentials' });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;
  audit.record(user.id, user.username, 'login.success', null, req.ip);
  res.redirect('/dashboard');
});

router.get('/logout', (req, res) => {
  if (req.session.userId) {
    audit.record(req.session.userId, req.session.username, 'logout', null, req.ip);
  }
  req.session.destroy(() => res.redirect('/login'));
});

module.exports = router;