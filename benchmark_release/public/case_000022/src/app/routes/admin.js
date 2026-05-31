'use strict';

const express     = require('express');
const crypto      = require('crypto');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { getDb }   = require('../db');
const auditSvc    = require('../services/auditService');

const router = express.Router();

// All admin routes require login + admin role
router.use(requireAuth, requireAdmin);

router.get('/users', (req, res) => {
  const users = getDb()
    .prepare('SELECT id, username, role, email, created_at FROM users ORDER BY id')
    .all();
  res.json(users);
});

router.post('/users', (req, res) => {
  const { username, password, role } = req.body;
  if (!username || !password) return res.status(400).json({ error: 'username and password required' });
  const allowed = ['admin', 'dev', 'viewer'];
  const r       = allowed.includes(role) ? role : 'dev';
  const hash    = crypto.createHash('sha256').update(password).digest('hex');
  try {
    getDb().prepare('INSERT INTO users (username, password_hash, role) VALUES (?,?,?)').run(username, hash, r);
    auditSvc.record(req.session.username, 'admin.user_create', 'user', username, { role: r });
    res.json({ ok: true });
  } catch (e) {
    if (e.message.includes('UNIQUE')) return res.status(409).json({ error: 'username taken' });
    throw e;
  }
});

router.delete('/users/:username', (req, res) => {
  if (req.params.username === req.session.username) {
    return res.status(400).json({ error: 'Cannot delete own account' });
  }
  getDb().prepare('DELETE FROM users WHERE username = ?').run(req.params.username);
  auditSvc.record(req.session.username, 'admin.user_delete', 'user', req.params.username, {});
  res.json({ ok: true });
});

router.get('/audit', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || '50', 10), 200);
  const logs  = auditSvc.recent(limit);
  res.json(logs);
});

router.get('/stats', (req, res) => {
  const db = getDb();
  res.json({
    users        : db.prepare('SELECT COUNT(*) AS n FROM users').get().n,
    issues_open  : db.prepare("SELECT COUNT(*) AS n FROM issues WHERE status='open'").get().n,
    issues_total : db.prepare('SELECT COUNT(*) AS n FROM issues').get().n,
    tasks_done   : db.prepare("SELECT COUNT(*) AS n FROM tasks WHERE status='done'").get().n,
    tasks_total  : db.prepare('SELECT COUNT(*) AS n FROM tasks').get().n,
  });
});

module.exports = router;