'use strict';

const express = require('express');
const router = express.Router();
const { getDb } = require('../db');

router.get('/', (req, res) => {
  const db = getDb();

  const recentRuns = db.prepare(`
    SELECT id, model_name, status, started_at, owner_id
    FROM training_runs
    ORDER BY started_at DESC
    LIMIT 8
  `).all();

  const stats = {
    totalRuns:    db.prepare('SELECT COUNT(*) as c FROM training_runs').get().c,
    activeRuns:   db.prepare("SELECT COUNT(*) as c FROM training_runs WHERE status='running'").get().c,
    totalModels:  db.prepare('SELECT COUNT(*) as c FROM model_registry').get().c,
    errorCount:   db.prepare("SELECT COUNT(*) as c FROM event_logs WHERE log_level='ERROR' AND recorded_at >= date('now','-1 day')").get().c,
  };

  const notifications = db.prepare(`
    SELECT id, message, created_at FROM notifications
    WHERE user_id = ? AND read = 0
    ORDER BY created_at DESC LIMIT 5
  `).all(req.session.userId);

  res.render('dashboard', {
    runs: recentRuns,
    stats,
    notifications,
    user: req.session.username,
    role: req.session.role
  });
});

module.exports = router;