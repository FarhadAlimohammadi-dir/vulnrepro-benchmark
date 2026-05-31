'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
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

  req.session.user = {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role
  };

  res.json({ ok: true, username: user.username, role: user.role });
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