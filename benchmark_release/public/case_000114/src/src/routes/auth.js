'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const { getDb } = require('../db');
const { logAction } = require('../services/audit');

const router = express.Router();

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/documents');
  res.render('login', { error: null });
});

router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password required.' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim());

  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    await logAction(null, 'LOGIN_FAILED', null, null, req.ip, `Failed login for: ${username}`);
    return res.render('login', { error: 'Invalid credentials.' });
  }

  req.session.user = { id: user.id, username: user.username, role: user.role };
  await logAction(user.id, 'LOGIN', null, null, req.ip, 'Successful login');
  res.redirect('/documents');
});

router.post('/register', async (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) {
    return res.status(400).json({ error: 'All fields required.' });
  }
  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters.' });
  }

  const db = getDb();
  const existing = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existing) {
    return res.status(409).json({ error: 'Username or email already taken.' });
  }

  const hash = bcrypt.hashSync(password, 10);
  const stmt = db.prepare('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)');
  stmt.run(username.trim(), email.trim(), hash, 'user');
  res.status(201).json({ message: 'Account created. Please log in.' });
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/auth/login');
  });
});

module.exports = router;