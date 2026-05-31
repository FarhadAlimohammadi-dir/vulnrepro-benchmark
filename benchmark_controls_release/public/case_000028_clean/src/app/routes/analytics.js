'use strict';

const express = require('express');
const router = express.Router();
const { getDb } = require('../db');
const logger = require('../services/logger');

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

const ANALYTICS_TABLES = {
  training_runs: 'SELECT id, model_name, status, started_at, finished_at FROM training_runs ORDER BY started_at DESC LIMIT ?',
  metrics: 'SELECT id, model_name, metric_name, metric_value, recorded_at FROM metrics ORDER BY recorded_at DESC LIMIT ?',
  datasets: 'SELECT id, name, source, created_at FROM datasets ORDER BY created_at DESC LIMIT ?',
};

function requireAnalyticsAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  if (req.session.role !== 'admin') {
    return res.status(403).json({ error: 'Administrator access required for analytics query interface.' });
  }
  next();
}

function parseLimit(value) {
  const parsed = parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return 100;
  return Math.min(parsed, 500);
}

router.get('/query', requireAnalyticsAdmin, (req, res) => {
  const table = String(req.query.table || '').toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(ANALYTICS_TABLES, table)) {
    return res.status(400).json({
      error: 'Unknown table',
      tables: Object.keys(ANALYTICS_TABLES),
    });
  }
  const limit = parseLimit(req.query.limit);
  const db = getDb();
  try {
    const rows = db.prepare(ANALYTICS_TABLES[table]).all(limit);
    logger.info(`Analytics list ${table} limit=${limit}`);
    res.json({ rows, count: rows.length, table });
  } catch (err) {
    logger.warn(`Analytics list error: ${err.message}`);
    res.status(500).json({ error: 'Query failed' });
  }
});

router.post('/query', requireAnalyticsAdmin, (req, res) => {
  const table = String((req.body && req.body.table) || '').toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(ANALYTICS_TABLES, table)) {
    return res.status(400).json({
      error: 'Unknown table',
      tables: Object.keys(ANALYTICS_TABLES),
    });
  }
  const limit = parseLimit(req.body && req.body.limit);
  const db = getDb();
  try {
    const rows = db.prepare(ANALYTICS_TABLES[table]).all(limit);
    res.json({ rows, count: rows.length, table });
  } catch (err) {
    res.status(500).json({ error: 'Query failed' });
  }
});

module.exports = router;
