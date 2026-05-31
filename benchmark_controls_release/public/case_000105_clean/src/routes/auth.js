'use strict';

const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const db = require('../db/database');

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('auth/login', { title: 'Login', error: null });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.render('auth/login', { title: 'Login', error: 'All fields are required.' });
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    return res.render('auth/login', { title: 'Login', error: 'Invalid credentials.' });
  }

  req.session.user = {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role
  };

  db.prepare(
    'INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)'
  ).run(user.id, 'LOGIN', 'auth', req.ip);

  res.redirect('/dashboard');
});

router.get('/register', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('auth/register', { title: 'Register', error: null });
});

router.post('/register', (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.render('auth/register', { title: 'Register', error: 'All fields are required.' });
  }

  if (password.length < 8) {
    return res.render('auth/register', { title: 'Register', error: 'Password must be at least 8 characters.' });
  }

  const existing = db.prepare(
    'SELECT id FROM users WHERE username = ? OR email = ?'
  ).get(username, email);

  if (existing) {
    return res.render('auth/register', { title: 'Register', error: 'Username or email already taken.' });
  }

  const hash = bcrypt.hashSync(password, 10);
  db.prepare(
    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)'
  ).run(username, email, hash);

  res.redirect('/auth/login');
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

module.exports = router;