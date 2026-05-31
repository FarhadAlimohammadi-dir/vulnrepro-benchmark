'use strict';

const express = require('express');
const { requireLogin, requireAdmin } = require('../middleware/auth');
const { getDb } = require('../models/db');
const { recentAudit } = require('../services/auditService');
const { agentState } = require('../services/agentState');
const router = express.Router();

router.use(requireLogin, requireAdmin);

// GET /admin — overview
router.get('/', (req, res) => {
  const db = getDb();
  const users     = db.prepare('SELECT id, username, display_name, email, role, last_login FROM users ORDER BY id').all();
  const execCount = db.prepare('SELECT COUNT(*) as c FROM exec_log').get().c;
  const wfCount   = db.prepare('SELECT COUNT(*) as c FROM workflows').get().c;
  const runCount  = db.prepare('SELECT COALESCE(SUM(run_count),0) as c FROM workflows').get().c;

  res.render('admin/index', {
    users,
    execCount,
    wfCount,
    runCount,
    agentState: {
      gatewayUrl: agentState.gatewayUrl,
      execApprovalsEnabled: agentState.execApprovalsEnabled,
      sandboxMode: agentState.sandboxMode,
      connectionStatus: agentState.connectionStatus
    },
    title: 'Admin'
  });
});

// GET /admin/audit — paginated audit log
router.get('/audit', (req, res) => {
  const page  = parseInt(req.query.page) || 1;
  const limit = 25;
  const db    = getDb();
  const total = db.prepare('SELECT COUNT(*) as c FROM audit_log').get().c;
  const rows  = db.prepare(
    'SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?'
  ).all(limit, (page - 1) * limit);

  res.render('admin/audit', {
    rows,
    page,
    limit,
    total,
    pages: Math.ceil(total / limit),
    title: 'Audit Log'
  });
});

// GET /admin/exec-log — execution history
router.get('/exec-log', (req, res) => {
  const db   = getDb();
  const rows = db.prepare('SELECT * FROM exec_log ORDER BY id DESC LIMIT 100').all();
  res.render('admin/exec_log', { rows, title: 'Exec Log' });
});

// POST /admin/users/:id/role — promote/demote user
router.post('/users/:id/role', (req, res) => {
  const { role } = req.body;
  const allowed  = ['user', 'operator', 'admin'];
  if (!allowed.includes(role)) return res.status(400).json({ error: 'invalid role' });
  const db = getDb();
  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, req.params.id);
  res.redirect('/admin');
});

module.exports = router;