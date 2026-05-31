'use strict';

const express          = require('express');
const { db }           = require('../db');
const { writeAudit }   = require('../middleware/audit');

const router = express.Router();

// GET /login
router.get('/login', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null });
});

// POST /login
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Please enter your username and password.' });
  }
  const user = db.prepare('SELECT * FROM users WHERE username=? AND password=?').get(username.trim(), password);
  if (!user) {
    writeAudit(null, 'LOGIN_FAILED', `username=${username}`, req.ip);
    return res.render('login', { error: 'Invalid credentials. Please try again.' });
  }
  req.session.userId      = user.id;
  req.session.username    = user.username;
  req.session.displayName = user.display_name;
  req.session.role        = user.role;
  writeAudit(user.id, 'USER_LOGIN', null, req.ip);
  res.redirect('/dashboard');
});

// GET /logout
router.get('/logout', (req, res) => {
  if (req.session.userId) writeAudit(req.session.userId, 'USER_LOGOUT', null, req.ip);
  req.session.destroy(() => res.redirect('/login'));
});

module.exports = router;