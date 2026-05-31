'use strict';

const express = require('express');
const router = express.Router();
const { getDb } = require('../db');

// GET /api/metrics — per-model metrics with optional filtering
router.get('/metrics', (req, res) => {
  const { model, run_id, limit } = req.query;
  const db = getDb();
  const safeLimit = Math.min(parseInt(limit, 10) || 50, 200);
  const conditions = [];
  const params = [];

  if (model && /^[a-zA-Z0-9_-]+$/.test(model)) {
    conditions.push('model_name = ?');
    params.push(model);
  }
  if (run_id && /^\d+$/.test(run_id)) {
    conditions.push('run_id = ?');
    params.push(parseInt(run_id, 10));
  }

  const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
  const rows = db.prepare(
    `SELECT id, model_name, run_id, metric_name, metric_value, recorded_at FROM metrics ${where} ORDER BY recorded_at DESC LIMIT ?`
  ).all(...params, safeLimit);

  res.json({ metrics: rows, count: rows.length });
});

// POST /api/logs/search — filtered event log search
router.post('/logs/search', (req, res) => {
  const { service, level, from_ts, actor } = req.body;
  const db = getDb();
  const allowedServices = ['trainer', 'evaluator', 'data-loader', 'api-gateway'];
  const allowedLevels   = ['INFO', 'WARN', 'ERROR', 'DEBUG'];
  const conditions = [];
  const params = [];

  if (service && allowedServices.includes(service)) {
    conditions.push('service_name = ?');
    params.push(service);
  }
  if (level && allowedLevels.includes(level)) {
    conditions.push('log_level = ?');
    params.push(level);
  }
  if (from_ts && /^\d{4}-\d{2}-\d{2}$/.test(from_ts)) {
    conditions.push('recorded_at >= ?');
    params.push(from_ts);
  }
  if (actor && /^[a-zA-Z0-9_-]+$/.test(actor)) {
    conditions.push('actor = ?');
    params.push(actor);
  }

  const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
  const rows = db.prepare(
    `SELECT id, service_name, log_level, message, actor, recorded_at FROM event_logs ${where} ORDER BY recorded_at DESC LIMIT 100`
  ).all(...params);

  res.json({ logs: rows, count: rows.length });
});

// GET /api/notifications — unread notifications for current user
router.get('/notifications', (req, res) => {
  const db = getDb();
  const rows = db.prepare(
    'SELECT id, message, created_at FROM notifications WHERE user_id = ? AND read = 0 ORDER BY created_at DESC'
  ).all(req.session.userId);
  res.json({ notifications: rows });
});

// POST /api/notifications/:id/read — mark notification read
router.post('/notifications/:id/read', (req, res) => {
  const nid = parseInt(req.params.id, 10);
  if (isNaN(nid)) return res.status(400).json({ error: 'Invalid ID' });
  const db = getDb();
  db.prepare('UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?')
    .run(nid, req.session.userId);
  res.json({ ok: true });
});

// GET /api/registry — model registry listing
router.get('/registry', (req, res) => {
  const { tags } = req.query;
  const db = getDb();
  let rows;
  if (tags && /^[a-zA-Z0-9_,.-]+$/.test(tags)) {
    // Exact tag filter using LIKE — safe parameterized
    rows = db.prepare(
      "SELECT id, model_name, version, artifact_path, description, tags, created_at FROM model_registry WHERE tags LIKE ? ORDER BY created_at DESC"
    ).all(`%${tags}%`);
  } else {
    rows = db.prepare(
      'SELECT id, model_name, version, artifact_path, description, tags, created_at FROM model_registry ORDER BY created_at DESC'
    ).all();
  }
  res.json({ models: rows });
});

module.exports = router;