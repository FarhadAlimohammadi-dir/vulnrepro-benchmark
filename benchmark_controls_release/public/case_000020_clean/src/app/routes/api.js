'use strict';

const express = require('express');
const router  = express.Router();
const crypto  = require('crypto');

const { db }             = require('../db');
const integrationService = require('../services/integrationService');
const auditService       = require('../services/auditService');

// ── GET /api/integrations — list caller's integrations ────────────────────────
router.get('/integrations', (req, res) => {
  const rows = db.prepare(
    'SELECT id, name, provider_type, client_id, status, scopes, created_at FROM integrations WHERE owner_id = ? ORDER BY created_at DESC'
  ).all(req.session.userId);
  res.json(rows);
});

// ── GET /api/integrations/:id — single integration detail ─────────────────────
router.get('/integrations/:id', (req, res) => {
  const row = integrationService.getByIdForOwner(req.params.id, req.session.userId);
  if (!row) return res.status(404).json({ ok: false, reason: 'not found' });
  res.json({ ok: true, integration: row });
});

// ── DELETE /api/integrations/:id ──────────────────────────────────────────────
router.delete('/integrations/:id', (req, res) => {
  const info = integrationService.remove(req.params.id, req.session.userId);
  if (info.changes > 0) {
    auditService.log(req.session.userId, 'integration_deleted_api', `id=${req.params.id}`);
    return res.json({ deleted: true });
  }
  res.status(404).json({ deleted: false, reason: 'not found' });
});

// ── GET /api/integrations/:id/status ─────────────────────────────────────────
router.get('/integrations/:id/status', (req, res) => {
  try {
    const row = db.prepare(
      'SELECT id, name, provider_type, status, last_sync_at, created_at FROM integrations WHERE id = ? AND owner_id = ?'
    ).get(req.params.id, req.session.userId);
    if (!row) return res.status(404).json({ ok: false, reason: 'not found' });
    res.json({ ok: true, integration: row });
  } catch (err) {
    console.error('[api] status error:', err.message);
    res.status(500).json({ ok: false, reason: 'internal error' });
  }
});

// ── POST /api/integrations/:id/sync — trigger a metadata refresh ──────────────
// perf: avoid extra round-trip when cache is warm — returns cached status if < 60s old
router.post('/integrations/:id/sync', (req, res) => {
  const row = integrationService.getByIdForOwner(req.params.id, req.session.userId);
  if (!row) return res.status(404).json({ ok: false, reason: 'not found' });

  if (row.last_sync_at) {
    const age = Date.now() - new Date(row.last_sync_at).getTime();
    if (age < 60_000) {
      return res.json({ ok: true, cached: true, last_sync_at: row.last_sync_at });
    }
  }

  integrationService.touchSyncTime(row.id);
  auditService.log(req.session.userId, 'integration_sync', `id=${row.id}`);
  res.json({ ok: true, cached: false, synced_at: new Date().toISOString() });
});

// ── GET /api/notifications — unread notification count ────────────────────────
router.get('/notifications', (req, res) => {
  const rows = db.prepare(
    'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 20'
  ).all(req.session.userId);
  res.json(rows);
});

// ── POST /api/notifications/:id/read ─────────────────────────────────────────
router.post('/notifications/:id/read', (req, res) => {
  db.prepare(
    'UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?'
  ).run(req.params.id, req.session.userId);
  res.json({ ok: true });
});

// ── GET /api/tokens — list API tokens ────────────────────────────────────────
router.get('/tokens', (req, res) => {
  const rows = db.prepare(
    'SELECT id, label, last_used, created_at FROM api_tokens WHERE user_id = ?'
  ).all(req.session.userId);
  res.json(rows);
});

// ── POST /api/tokens — generate a new API token ───────────────────────────────
router.post('/tokens', (req, res) => {
  const { label } = req.body;
  const token = 'tbk_' + crypto.randomBytes(18).toString('hex');
  const result = db.prepare(
    'INSERT INTO api_tokens (user_id, token, label) VALUES (?, ?, ?)'
  ).run(req.session.userId, token, (label || 'Unnamed token').slice(0, 80));
  auditService.log(req.session.userId, 'token_created', `id=${result.lastInsertRowid}`);
  res.status(201).json({ ok: true, token });
});

// ── DELETE /api/tokens/:id ────────────────────────────────────────────────────
router.delete('/tokens/:id', (req, res) => {
  const info = db.prepare(
    'DELETE FROM api_tokens WHERE id = ? AND user_id = ?'
  ).run(req.params.id, req.session.userId);
  res.json({ deleted: info.changes > 0 });
});

module.exports = router;