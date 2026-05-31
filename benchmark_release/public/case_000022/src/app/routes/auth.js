'use strict';

const express = require('express');
const crypto  = require('crypto');
const { getDb } = require('../db');
const auditSvc  = require('../services/auditService');

const router = express.Router();

router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, next: req.query.next || '/dashboard' });
});

router.post('/login', (req, res) => {
  const { username, password, next } = req.body;
  const redirect = (next && next.startsWith('/')) ? next : '/dashboard';

  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', next: redirect });
  }

  const db   = getDb();
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password_hash = ?').get(username, hash);

  if (!user) {
    auditSvc.record(username, 'auth.fail', 'user', null, { reason: 'bad credentials' });
    return res.render('login', { error: 'Invalid username or password.', next: redirect });
  }

  req.session.regenerate((err) => {
    if (err) return res.status(500).render('error', { code: 500, message: 'Session error' });
    req.session.userId   = user.id;
    req.session.username = user.username;
    req.session.role     = user.role;
    auditSvc.record(user.username, 'auth.login', 'user', String(user.id), {});
    res.redirect(redirect);
  });
});

router.get('/logout', (req, res) => {
  const actor = req.session.username;
  req.session.destroy(() => {
    auditSvc.record(actor, 'auth.logout', 'user', null, {});
    res.redirect('/login');
  });
});

module.exports = router;