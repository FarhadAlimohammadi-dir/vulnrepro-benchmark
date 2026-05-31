'use strict';

const express                   = require('express');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const userService               = require('../services/userService');
const db                        = require('../db');
const logger                    = require('../services/logger');

const router = express.Router();
router.use(requireAuth);
router.use(requireAdmin);

// ── GET /api/admin/users ──────────────────────────────────────────────────────
router.get('/users', (req, res) => {
  const page   = parseInt(req.query.page   || '1',  10);
  const limit  = parseInt(req.query.limit  || '25', 10);
  const search = (req.query.search || '').trim();
  const result = userService.listUsers({ page, limit, search });
  res.json(result.rows);
});

// ── PATCH /api/admin/users/:id/role ──────────────────────────────────────────
router.patch('/users/:id/role', (req, res) => {
  const { role } = req.body;
  try {
    userService.setUserRole(req.params.id, role);
    db.prepare(
      'INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)'
    ).run(req.session.userId, 'role_change',
      JSON.stringify({ targetUserId: req.params.id, newRole: role }));
    res.json({ ok: true });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// ── GET /api/admin/audit ──────────────────────────────────────────────────────
router.get('/audit', (req, res) => {
  const page  = parseInt(req.query.page  || '1',  10);
  const limit = parseInt(req.query.limit || '50', 10);
  const offset = (page - 1) * limit;

  const rows = db.prepare(
    `SELECT al.*, u.username
     FROM audit_log al
     LEFT JOIN users u ON u.id = al.user_id
     ORDER BY al.created_at DESC
     LIMIT ? OFFSET ?`
  ).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as c FROM audit_log').get().c;
  res.json({ rows, total, page, limit });
});

// ── GET /api/admin/stats ──────────────────────────────────────────────────────
router.get('/stats', (req, res) => {
  const userCount     = db.prepare('SELECT COUNT(*) as c FROM users').get().c;
  const pipelineCount = db.prepare('SELECT COUNT(*) as c FROM pipelines').get().c;
  const runCount      = db.prepare('SELECT COUNT(*) as c FROM pipeline_runs').get().c;
  const connCount     = db.prepare('SELECT COUNT(*) as c FROM connectors').get().c;

  const recentRuns = db.prepare(
    `SELECT pr.*, p.name AS pipeline_name, u.username
     FROM pipeline_runs pr
     JOIN pipelines p ON p.id = pr.pipeline_id
     JOIN users u ON u.id = p.owner_id
     ORDER BY pr.started_at DESC LIMIT 10`
  ).all();

  res.json({ userCount, pipelineCount, runCount, connCount, recentRuns });
});

// ── DELETE /api/admin/users/:id ───────────────────────────────────────────────
router.delete('/users/:id', (req, res) => {
  const targetId = parseInt(req.params.id, 10);
  if (targetId === req.session.userId) {
    return res.status(400).json({ error: 'Cannot delete your own account' });
  }
  const r = db.prepare('DELETE FROM users WHERE id = ?').run(targetId);
  if (r.changes === 0) return res.status(404).json({ error: 'User not found' });

  db.prepare(
    'INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)'
  ).run(req.session.userId, 'user_deleted', JSON.stringify({ deletedUserId: targetId }));

  logger.info('Admin deleted user', { adminId: req.session.userId, deletedUserId: targetId });
  res.json({ ok: true });
});

// ── GET /api/admin/settings ───────────────────────────────────────────────────
router.get('/settings', (req, res) => {
  const rows = db.prepare('SELECT key, value FROM settings').all();
  const settings = {};
  rows.forEach(r => { settings[r.key] = r.value; });
  res.json(settings);
});

// ── PUT /api/admin/settings ───────────────────────────────────────────────────
router.put('/settings', (req, res) => {
  const allowed = ['site_name', 'max_pipelines', 'agent_model', 'mcp_timeout_ms', 'audit_retention_days'];
  const updates = req.body || {};
  const stmt = db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)');
  const persist = db.transaction((kv) => {
    for (const [k, v] of Object.entries(kv)) {
      if (allowed.includes(k)) stmt.run(k, String(v));
    }
  });
  persist(updates);
  logger.info('Settings updated', { adminId: req.session.userId });
  res.json({ ok: true });
});

module.exports = router;