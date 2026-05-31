'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware');

const router = express.Router();
router.use(requireAuth);

// GET /user/profile - get current user profile
router.get('/profile', (req, res) => {
  const db = getDb();
  const user = db.prepare('SELECT id, username, email, role, created_at, last_login FROM users WHERE id = ?')
    .get(req.session.user.id);
  res.json({ user });
});

// PUT /user/profile - update profile
router.put('/profile', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const { email, current_password, new_password } = req.body;

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });

  const updates = {};

  if (email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({ error: 'Invalid email format' });
    }
    const existing = db.prepare('SELECT id FROM users WHERE email = ? AND id != ?').get(email, userId);
    if (existing) return res.status(409).json({ error: 'Email already in use' });
    updates.email = email;
  }

  if (new_password) {
    if (!current_password) {
      return res.status(400).json({ error: 'current_password required to change password' });
    }
    if (!bcrypt.compareSync(current_password, user.password_hash)) {
      return res.status(401).json({ error: 'Current password is incorrect' });
    }
    if (new_password.length < 8) {
      return res.status(400).json({ error: 'New password must be at least 8 characters' });
    }
    updates.password_hash = bcrypt.hashSync(new_password, 10);
  }

  if (Object.keys(updates).length === 0) {
    return res.status(400).json({ error: 'Nothing to update' });
  }

  const fields = Object.keys(updates).map(k => `${k} = ?`).join(', ');
  db.prepare(`UPDATE users SET ${fields} WHERE id = ?`).run(...Object.values(updates), userId);

  if (updates.email) {
    req.session.user.email = updates.email;
  }

  res.json({ message: 'Profile updated' });
});

module.exports = router;