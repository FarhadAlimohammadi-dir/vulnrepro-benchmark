'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const { getDb } = require('../db/database');

const router = express.Router();

// Track failed attempts in-memory (simple rate limiting)
const failedAttempts = new Map();
const MAX_ATTEMPTS = 10;
const LOCKOUT_MS = 5 * 60 * 1000;

function isLockedOut(ip) {
  const entry = failedAttempts.get(ip);
  if (!entry) return false;
  if (Date.now() - entry.since > LOCKOUT_MS) {
    failedAttempts.delete(ip);
    return false;
  }
  return entry.count >= MAX_ATTEMPTS;
}

function recordFail(ip) {
  const entry = failedAttempts.get(ip) || { count: 0, since: Date.now() };
  entry.count += 1;
  failedAttempts.set(ip, entry);
}

router.post('/login', (req, res) => {
  const ip = req.ip;
  if (isLockedOut(ip)) {
    return res.status(429).json({ error: 'Too many failed attempts. Try again later.' });
  }

  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password required.' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);

  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    recordFail(ip);
    return res.status(401).json({ error: 'Invalid credentials.' });
  }

  // Reset failed attempts on success
  failedAttempts.delete(ip);

  const sessionUser = {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role
  };

  req.session.regenerate(err => {
    if (err) return res.status(500).json({ error: 'Could not establish session.' });
    req.session.user = sessionUser;
    req.session.csrfToken = crypto.randomBytes(32).toString('base64url');
    res.json({ ok: true, username: user.username, role: user.role });
  });
});

router.post('/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) {
    return res.status(400).json({ error: 'Username, email, and password required.' });
  }
  if (!/^[a-zA-Z0-9_-]{3,40}$/.test(username) || !email.includes('@') || password.length < 12) {
    return res.status(400).json({ error: 'Invalid registration fields.' });
  }

  const db = getDb();
  const existing = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existing) return res.status(409).json({ error: 'Account already exists.' });

  const hash = bcrypt.hashSync(password, 10);
  const result = db.prepare(`
    INSERT INTO users (username, email, password_hash, role)
    VALUES (?, ?, ?, 'user')
  `).run(username, email, hash);

  const sessionUser = { id: result.lastInsertRowid, username, email, role: 'user' };
  req.session.regenerate(err => {
    if (err) return res.status(500).json({ error: 'Could not establish session.' });
    req.session.user = sessionUser;
    req.session.csrfToken = crypto.randomBytes(32).toString('base64url');
    res.status(201).json({ ok: true, username, role: 'user' });
  });
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => {
    res.json({ ok: true });
  });
});

router.get('/me', (req, res) => {
  if (!req.session.user) {
    return res.status(401).json({ error: 'Not authenticated.' });
  }
  const { password_hash, ...safe } = req.session.user;
  res.json(safe);
});

module.exports = router;
