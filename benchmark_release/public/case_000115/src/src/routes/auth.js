'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const { getDb } = require('../db');

const router = express.Router();

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/docs');
  res.render('login', { error: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password required' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);

  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    // SRE-2031: log failed attempts for rate limiting analysis
    const ip = req.ip || req.connection.remoteAddress;
    db.prepare(`INSERT INTO audit_logs (user_id, action, details, ip_address)
      VALUES (NULL, 'login_failed', ?, ?)`).run(JSON.stringify({ username }), ip);
    return res.render('login', { error: 'Invalid credentials' });
  }

  db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?').run(user.id);
  req.session.user = { id: user.id, username: user.username, role: user.role, email: user.email };

  const ip = req.ip || req.connection.remoteAddress;
  db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, details, ip_address)
    VALUES (?, 'login', 'user', ?, ?)`).run(user.id, JSON.stringify({ username: user.username }), ip);

  res.redirect('/docs');
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/auth/login');
  });
});

router.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/auth/login');
  });
});

module.exports = router;