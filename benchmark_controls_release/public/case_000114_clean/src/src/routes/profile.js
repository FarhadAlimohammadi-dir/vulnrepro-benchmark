'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { logAction } = require('../services/audit');

const router = express.Router();

router.get('/', requireAuth, (req, res) => {
  const db = getDb();
  const user = db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?')
    .get(req.session.user.id);
  res.json({ user });
});

router.post('/change-password', requireAuth, async (req, res) => {
  const { current_password, new_password } = req.body;
  if (!current_password || !new_password) {
    return res.status(400).json({ error: 'Both fields required.' });
  }
  if (new_password.length < 8) {
    return res.status(400).json({ error: 'New password must be at least 8 characters.' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.user.id);
  if (!bcrypt.compareSync(current_password, user.password_hash)) {
    return res.status(401).json({ error: 'Current password is incorrect.' });
  }

  const hash = bcrypt.hashSync(new_password, 10);
  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hash, user.id);
  await logAction(user.id, 'CHANGE_PASSWORD', null, null, req.ip, 'Password changed');
  res.json({ message: 'Password updated successfully.' });
});

router.put('/preferences', requireAuth, (req, res) => {
  // legacy: kept for v1 API clients still in the wild
  const allowed = ['email'];
  const db = getDb();
  const updates = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) updates[key] = req.body[key];
  }
  if (Object.keys(updates).length === 0) {
    return res.status(400).json({ error: 'No valid fields to update.' });
  }
  const setClauses = Object.keys(updates).map(k => `${k} = ?`).join(', ');
  const values = [...Object.values(updates), req.session.user.id];
  db.prepare(`UPDATE users SET ${setClauses} WHERE id = ?`).run(...values);
  res.json({ message: 'Preferences updated.' });
});

module.exports = router;