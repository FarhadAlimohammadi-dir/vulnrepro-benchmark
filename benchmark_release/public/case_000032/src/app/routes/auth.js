'use strict';

const express = require('express');
const router = express.Router();
const { createSession, revokeSession } = require('../services/tokenService');
const { logAuditEvent } = require('../services/auditService');
const { optionalAuth } = require('../middleware/auth');

router.get('/login', optionalAuth, (req, res) => {
  if (req.user) return res.redirect('/dashboard');
  res.render('login', {
    title: 'Sign In',
    user: null,
    error: null,
    redirect: req.query.redirect || '/dashboard'
  });
});

router.post('/login', (req, res) => {
  const { username, password, redirect } = req.body;
  const db = req.db;

  if (!username || !password) {
    return res.render('login', {
      title: 'Sign In',
      user: null,
      error: 'Username and password are required.',
      redirect: redirect || '/dashboard'
    });
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1')
    .get(username.trim(), password);

  if (!user) {
    logAuditEvent(db, null, 'LOGIN_FAILED', 'user', null, `Failed login attempt for username: ${username}`, req.ip);
    return res.render('login', {
      title: 'Sign In',
      user: null,
      error: 'Invalid username or password.',
      redirect: redirect || '/dashboard'
    });
  }

  const sid = createSession(db, user.id, req.ip, req.get('user-agent'));
  db.prepare('UPDATE users SET last_login = ? WHERE id = ?').run(Date.now(), user.id);

  logAuditEvent(db, user.id, 'LOGIN', 'session', sid, `Successful login from ${req.ip}`, req.ip);

  res.cookie('sid', sid, {
    httpOnly: true,
    maxAge: 86400000 * 7,
    sameSite: 'lax'
  });

  const redirectTo = redirect && redirect.startsWith('/') ? redirect : '/dashboard';
  res.redirect(redirectTo);
});

router.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  const db = req.db;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required.' });
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1')
    .get(username.trim(), password);

  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const sid = createSession(db, user.id, req.ip, req.get('user-agent'));
  db.prepare('UPDATE users SET last_login = ? WHERE id = ?').run(Date.now(), user.id);

  res.cookie('sid', sid, { httpOnly: true, maxAge: 86400000 * 7 });
  res.json({ success: true, user_id: user.id });
});

router.post('/logout', (req, res) => {
  const sid = req.cookies && req.cookies.sid;
  if (sid) {
    revokeSession(req.db, sid);
  }
  res.clearCookie('sid');
  res.redirect('/login');
});

module.exports = router;