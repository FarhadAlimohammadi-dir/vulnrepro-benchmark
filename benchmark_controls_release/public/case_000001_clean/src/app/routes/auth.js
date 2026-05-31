'use strict';

const express = require('express');
const crypto = require('crypto');
const { getDb, hashPassword } = require('../models/db');
const { writeAudit } = require('../services/auditService');
const router = express.Router();

router.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, info: req.query.info || null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', info: null });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(String(username).trim().toLowerCase());
  if (!user) {
    return res.render('login', { error: 'Invalid credentials.', info: null });
  }

  const hash = hashPassword(password, user.salt);
  if (hash !== user.password_hash) {
    writeAudit(username, 'login.fail', 'session', '{}', req.ip);
    return res.render('login', { error: 'Invalid credentials.', info: null });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;
  req.session.display  = user.display_name;

  db.prepare("UPDATE users SET last_login = datetime('now') WHERE id = ?").run(user.id);
  writeAudit(user.username, 'login.ok', 'session', '{}', req.ip);

  res.redirect('/dashboard');
});

router.get('/logout', (req, res) => {
  const actor = req.session.username || 'unknown';
  req.session.destroy(() => {
    res.redirect('/login?info=Signed+out+successfully');
  });
});

// ── Profile ────────────────────────────────────────────────────────────────────
router.get('/profile', (req, res) => {
  if (!req.session.userId) return res.redirect('/login');
  const db = getDb();
  const user = db.prepare('SELECT id, username, display_name, email, role, avatar_initials, created_at, last_login FROM users WHERE id = ?').get(req.session.userId);
  const notifs = db.prepare('SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10').all(req.session.userId);
  res.render('profile', { user, notifs });
});

router.post('/profile', (req, res) => {
  if (!req.session.userId) return res.redirect('/login');
  const { display_name, email } = req.body;
  const db = getDb();
  db.prepare('UPDATE users SET display_name = ?, email = ? WHERE id = ?').run(
    String(display_name || '').trim(),
    String(email || '').trim(),
    req.session.userId
  );
  writeAudit(req.session.username, 'profile.update', `user:${req.session.userId}`, '{}', req.ip);
  req.session.display = display_name;
  res.redirect('/profile');
});

module.exports = router;