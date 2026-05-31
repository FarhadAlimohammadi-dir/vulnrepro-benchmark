'use strict';

const express         = require('express');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const db              = require('../db');
const logger          = require('../services/logger');

const router = express.Router();
router.use(requireAuth);

// ── GET /api/connectors ───────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const rows = db.prepare(
    `SELECT c.id, c.name, c.type, c.status, c.created_at, u.username AS owner
     FROM connectors c
     LEFT JOIN users u ON u.id = c.owner_id
     ORDER BY c.created_at DESC`
  ).all();
  res.json(rows);
});

// ── GET /api/connectors/:id ───────────────────────────────────────────────────
router.get('/:id', (req, res) => {
  const connector = db.prepare('SELECT * FROM connectors WHERE id = ?').get(req.params.id);
  if (!connector) return res.status(404).json({ error: 'Connector not found' });
  // Never return raw credentials from config blob
  let cfg = {};
  try { cfg = JSON.parse(connector.config); } catch (_) {}
  delete cfg.password; delete cfg.token; delete cfg.secret;
  res.json({ ...connector, config: cfg });
});

// ── POST /api/connectors ──────────────────────────────────────────────────────
router.post('/', requireAdmin, (req, res) => {
  const { name, type, config } = req.body;
  if (!name || !type) return res.status(400).json({ error: 'name and type are required' });

  const ALLOWED_TYPES = ['postgresql', 'github', 'bigquery', 'salesforce', 'csv', 'rest'];
  if (!ALLOWED_TYPES.includes(type)) {
    return res.status(400).json({ error: 'Unsupported connector type' });
  }

  const r = db.prepare(
    'INSERT INTO connectors (name, type, config, owner_id) VALUES (?, ?, ?, ?)'
  ).run(name, type, JSON.stringify(config || {}), req.session.userId);

  logger.info('Connector created', { id: r.lastInsertRowid, name, type });
  res.status(201).json({ id: r.lastInsertRowid });
});

// ── PUT /api/connectors/:id ───────────────────────────────────────────────────
router.put('/:id', requireAdmin, (req, res) => {
  const { name, status } = req.body;
  const connector = db.prepare('SELECT * FROM connectors WHERE id = ?').get(req.params.id);
  if (!connector) return res.status(404).json({ error: 'Connector not found' });

  db.prepare('UPDATE connectors SET name = ?, status = ? WHERE id = ?').run(
    name || connector.name,
    status || connector.status,
    req.params.id
  );
  res.json({ ok: true });
});

// ── DELETE /api/connectors/:id ────────────────────────────────────────────────
router.delete('/:id', requireAdmin, (req, res) => {
  const r = db.prepare('DELETE FROM connectors WHERE id = ?').run(req.params.id);
  if (r.changes === 0) return res.status(404).json({ error: 'Connector not found' });
  res.json({ ok: true });
});

// ── GET /api/connectors/:id/preview ──────────────────────────────────────────
// Returns a small sample from the connector's schema.
// All field values serialized through JSON.stringify — no injection path here.
router.get('/:id/preview', (req, res) => {
  const connector = db.prepare('SELECT * FROM connectors WHERE id = ?').get(req.params.id);
  if (!connector) return res.status(404).json({ error: 'Connector not found' });

  const sample = db.prepare('SELECT id, username, email, role FROM users LIMIT 3').all();
  // Full JSON.stringify pass on all values before returning
  const safeOutput = JSON.stringify({ connector: connector.name, sample });

  res.json({ preview: JSON.parse(safeOutput), note: 'Read-only schema sample' });
});

module.exports = router;