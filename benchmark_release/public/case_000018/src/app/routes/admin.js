'use strict';

const express   = require('express');
const { getDb } = require('../db');
const audit     = require('../services/auditService');

const router = express.Router();

// ── Admin dashboard ───────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const db      = getDb();
  const users   = db.prepare('SELECT id, username, plan, is_admin, created_at FROM users ORDER BY id').all();
  const { imgCount }  = db.prepare('SELECT COUNT(*) AS imgCount FROM images').get();
  const { userCount } = db.prepare('SELECT COUNT(*) AS userCount FROM users').get();
  const { shareCount } = db.prepare('SELECT COUNT(*) AS shareCount FROM shares').get();
  const logs    = audit.recent(30);

  res.render('admin', { users, imgCount, userCount, shareCount, logs });
});

// ── Toggle admin status ───────────────────────────────────────────────────────
router.post('/users/:id/toggle-admin', (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  if (user.id === req.session.userId) {
    return res.status(400).json({ error: 'You cannot modify your own admin status.' });
  }
  const newVal = user.is_admin ? 0 : 1;
  db.prepare('UPDATE users SET is_admin = ? WHERE id = ?').run(newVal, user.id);
  audit.record(req.session.userId, 'toggle_admin', 'user', user.id,
    `Set is_admin=${newVal} for ${user.username}`, req.ip);
  res.redirect('/admin');
});

// ── Change user plan ──────────────────────────────────────────────────────────
router.post('/users/:id/plan', (req, res) => {
  const { plan } = req.body;
  const allowed  = ['free', 'pro', 'enterprise'];
  if (!allowed.includes(plan)) {
    return res.status(400).json({ error: 'Invalid plan.' });
  }
  const db   = getDb();
  const user = db.prepare('SELECT id, username FROM users WHERE id = ?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  db.prepare('UPDATE users SET plan = ? WHERE id = ?').run(plan, user.id);
  audit.record(req.session.userId, 'plan_change', 'user', user.id,
    `Changed plan to ${plan} for ${user.username}`, req.ip);
  res.redirect('/admin');
});

// ── Delete user ───────────────────────────────────────────────────────────────
router.post('/users/:id/delete', (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT id, username FROM users WHERE id = ?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  if (user.id === req.session.userId) {
    return res.status(400).json({ error: 'Cannot delete your own account.' });
  }
  db.prepare('DELETE FROM images WHERE owner_id = ?').run(user.id);
  db.prepare('DELETE FROM collections WHERE owner_id = ?').run(user.id);
  db.prepare('DELETE FROM users WHERE id = ?').run(user.id);
  audit.record(req.session.userId, 'delete_user', 'user', user.id,
    `Deleted user account: ${user.username}`, req.ip);
  res.redirect('/admin');
});

module.exports = router;