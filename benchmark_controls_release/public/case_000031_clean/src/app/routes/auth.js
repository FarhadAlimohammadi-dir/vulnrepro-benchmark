'use strict';

const express = require('express');
const db = require('../db');
const audit = require('../services/auditService');

const router = express.Router();

router.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('index', { error: null });
});

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('index', { error: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.render('index', { error: 'Username and password are required.' });
  }

  const user = db.getUserByUsername(username.trim());

  if (!user || user.password !== password) {
    audit.log(req, 'auth.failure', `username:${username}`, { reason: 'bad credentials' });
    return res.render('index', { error: 'Invalid username or password.' });
  }

  db.updateLastLogin(user.id);
  req.session.user = { id: user.id, username: user.username, role: user.role };
  audit.log(req, 'user.login', `user:${user.id}`, { username: user.username });
  res.redirect('/dashboard');
});

router.get('/logout', (req, res) => {
  if (req.session.user) {
    audit.log(req, 'user.logout', `user:${req.session.user.id}`, {});
  }
  req.session.destroy(() => res.redirect('/'));
});

module.exports = router;