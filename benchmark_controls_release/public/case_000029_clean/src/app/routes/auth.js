'use strict';

const express     = require('express');
const router      = express.Router();
const userService = require('../services/userService');
const { logAudit } = require('../services/docService');

router.get('/', (_req, res) => res.redirect('/login'));

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('login', { error: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password || username.length > 64 || password.length > 128) {
    return res.render('login', { error: 'Please provide valid credentials.' });
  }

  const user = userService.findByCredentials(username.trim(), password);
  if (!user) {
    return res.render('login', { error: 'Incorrect username or password.' });
  }

  req.session.user = { id: user.id, username: user.username, role: user.role, display_name: user.display_name };
  logAudit(user.id, 'login', null, req.ip);
  res.redirect('/dashboard');
});

router.get('/logout', (req, res) => {
  if (req.session.user) {
    logAudit(req.session.user.id, 'logout', null, req.ip);
  }
  req.session.destroy(() => res.redirect('/login'));
});

router.get('/dashboard', (req, res) => {
  if (!req.session.user) return res.redirect('/login');
  res.redirect('/docs');
});

module.exports = router;