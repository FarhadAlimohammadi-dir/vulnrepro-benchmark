'use strict';

const router = require('express').Router();
const usersSvc = require('../services/users');
const auditLog = require('../services/audit');
const logger = require('../services/logger');

router.get('/login', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, flash: res.locals.flash });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', flash: null });
  }
  if (typeof username !== 'string' || username.length > 64) {
    return res.render('login', { error: 'Invalid input.', flash: null });
  }

  const user = usersSvc.getByCredentials(username.trim(), password);
  if (!user) {
    logger.warn(`Failed login attempt for username: ${username}`);
    return res.render('login', { error: 'Invalid username or password.', flash: null });
  }

  req.session.regenerate(err => {
    if (err) return res.render('login', { error: 'Session error. Please try again.', flash: null });
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.role = user.role;
    auditLog.record(user.id, 'auth.login', `User ${user.username} signed in`);
    res.redirect('/dashboard');
  });
});

router.get('/logout', (req, res) => {
  if (req.session && req.session.userId) {
    auditLog.record(req.session.userId, 'auth.logout', `User ${req.session.username} signed out`);
  }
  req.session.destroy(() => res.redirect('/login'));
});

module.exports = router;