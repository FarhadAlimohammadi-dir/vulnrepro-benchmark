'use strict';

const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { getDb } = require('../models/db');
const { getGatewayStatus } = require('../services/gatewayService');
const { listWorkflows } = require('../services/workflowService');
const router = express.Router();

router.get('/dashboard', requireLogin, (req, res) => {
  const db = getDb();
  const { rows: workflows } = listWorkflows(req.session.userId, { limit: 5 });
  const recentRuns = db.prepare(
    `SELECT wr.*, w.name as workflow_name
     FROM workflow_runs wr JOIN workflows w ON w.id = wr.workflow_id
     WHERE w.owner_id = ? ORDER BY wr.ran_at DESC LIMIT 10`
  ).all(req.session.userId);

  const stats = {
    totalWorkflows: db.prepare('SELECT COUNT(*) as c FROM workflows WHERE owner_id = ?').get(req.session.userId).c,
    totalRuns: db.prepare(
      'SELECT COALESCE(SUM(run_count),0) as c FROM workflows WHERE owner_id = ?'
    ).get(req.session.userId).c,
    pluginCount: db.prepare('SELECT COUNT(*) as c FROM plugins WHERE owner_id = ?').get(req.session.userId).c
  };

  const notifCount = db.prepare(
    'SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND read = 0'
  ).get(req.session.userId).c;

  const gateway = getGatewayStatus();

  res.render('dashboard', {
    workflows,
    recentRuns,
    stats,
    gateway,
    notifCount,
    title: 'Dashboard'
  });
});

module.exports = router;