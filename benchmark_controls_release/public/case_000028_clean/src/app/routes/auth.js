'use strict';

const express = require('express');
const router = express.Router();
const { getUserByCredentials, updateLastLogin } = require('../services/userService');
const { record } = require('../services/auditService');
const logger = require('../services/logger');

router.get('/', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

router.get('/login', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: res.locals.flash || null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password || typeof username !== 'string' || typeof password !== 'string') {
    return res.render('login', { error: 'Username and password are required.' });
  }
  const clean = username.trim().toLowerCase();
  if (clean.length < 2 || clean.length > 64) {
    return res.render('login', { error: 'Invalid credentials.' });
  }

  const user = getUserByCredentials(clean, password.trim());
  if (!user) {
    logger.warn(`Failed login attempt for username: ${clean} from ${req.ip}`);
    return res.render('login', { error: 'Invalid credentials.' });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;

  updateLastLogin(user.id);
  record({ actorId: user.id, actorName: user.username, action: 'LOGIN', resource: `users/${user.id}`, detail: 'Session started', ipAddr: req.ip });
  logger.info(`User ${user.username} logged in from ${req.ip}`);

  res.redirect('/dashboard');
});

router.post('/logout', (req, res) => {
  const name = req.session.username;
  const id   = req.session.userId;
  req.session.destroy(() => {
    if (name) record({ actorId: id, actorName: name, action: 'LOGOUT', resource: `users/${id}`, detail: 'Session ended' });
    res.redirect('/login');
  });
});

module.exports = router;