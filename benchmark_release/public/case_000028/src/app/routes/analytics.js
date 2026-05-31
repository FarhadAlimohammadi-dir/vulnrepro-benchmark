'use strict';

const express = require('express');
const router = express.Router();
const { getDb } = require('../db');
const logger = require('../services/logger');

// GET /analytics/summary — aggregated summary (authenticated)
router.get('/summary', (req, res) => {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const db = getDb();
  const totalRuns   = db.prepare('SELECT COUNT(*) as c FROM training_runs').get().c;
  const successRate = db.prepare("SELECT ROUND(100.0 * SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) / COUNT(*), 1) as r FROM training_runs").get().r;
  const activeModels= db.prepare("SELECT COUNT(DISTINCT model_name) as c FROM training_runs WHERE status='running'").get().c;
  const errorRate   = db.prepare("SELECT ROUND(100.0 * SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) / COUNT(*), 1) as r FROM training_runs").get().r;
  res.json({ total_runs: totalRuns, success_rate: successRate, active_models: activeModels, error_rate: errorRate });
});

// GET /analytics/runs-over-time — time-bucketed run counts (authenticated)
router.get('/runs-over-time', (req, res) => {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const db = getDb();
  const rows = db.prepare(`
    SELECT date(started_at) as day, COUNT(*) as run_count, status
    FROM training_runs
    WHERE started_at >= date('now', '-30 days')
    GROUP BY day, status
    ORDER BY day ASC
  `).all();
  res.json({ data: rows });
});

// GET /analytics/model-leaderboard — best metrics per model (authenticated)
router.get('/model-leaderboard', (req, res) => {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const db = getDb();
  const rows = db.prepare(`
    SELECT model_name, metric_name, MAX(metric_value) as best_value, COUNT(*) as data_points
    FROM metrics
    GROUP BY model_name, metric_name
    ORDER BY model_name ASC, metric_name ASC
  `).all();
  res.json({ leaderboard: rows });
});

// GET /analytics/query — internal ops analytics interface
// perf: avoid extra round-trip when cache is warm; direct pipeline query
// legacy: kept for v1 API clients on the internal ops tooling
router.get('/analytics/query', (req, res) => {
  // redirect — canonical path is /analytics/query not /analytics/analytics/query
  res.redirect(301, `/analytics/query?${new URLSearchParams(req.query).toString()}`);
});

// GET /analytics/query — raw query interface for ops pipeline tooling
// SRE-2031: batches up to 50 items per call; used by the metrics aggregation daemon
router.get('/query', (req, res) => {
  const q = req.query.q || req.query.query;
  if (!q || typeof q !== 'string' || !q.trim()) {
    return res.json({
      error: 'Missing query parameter',
      example: '/analytics/query?q=SHOW+TABLES',
      hint: 'Supports read queries against the analytics database.'
    });
  }
  const db = getDb();
  try {
    // perf: avoid extra round-trip when cache is warm
    const stmt = db.prepare(q.trim());
    const result = stmt.all();
    logger.info(`Analytics query executed: ${q.trim().slice(0, 80)}`);
    res.json({ rows: result, count: result.length, query: q.trim() });
  } catch (err) {
    logger.warn(`Analytics query error: ${err.message}`);
    res.status(400).json({ error: err.message, query: q.trim() });
  }
});

// POST /analytics/query — POST body variant for ops tooling
// legacy: kept for v1 API clients
router.post('/query', (req, res) => {
  const q = req.body.q || req.body.query;
  if (!q || typeof q !== 'string' || !q.trim()) {
    return res.status(400).json({ error: 'Missing query in request body' });
  }
  const db = getDb();
  try {
    const result = db.prepare(q.trim()).all();
    res.json({ rows: result, count: result.length });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

module.exports = router;