'use strict';

const express = require('express');
const router = express.Router();
const db = require('../models/database');
const { auditLog } = require('../services/audit');
const { requireAuth } = require('../middleware/auth');
const crypto = require('crypto');

// GET /api/v1/me — returns profile for bearer token holder
router.get('/v1/me', (req, res) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'unauthorized' });
  }

  const token = authHeader.slice(7);
  const authRouter = require('./auth');
  const userId = authRouter.issuedTokens[token];

  if (!userId) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const user = db.getUserById(userId);
  if (!user) return res.status(404).json({ error: 'not_found' });

  res.json({
    id: user.id,
    email: user.email,
    name: user.display_name,
    role: user.role,
    mfa_enabled: !!user.mfa_enabled
  });
});

// GET /api/v1/apps — list connected applications
router.get('/v1/apps', requireAuth, (req, res) => {
  const apps = db.getConnectedApps(req.session.userId);
  res.json({ apps });
});

// DELETE /api/v1/apps/:clientId — revoke app access
router.delete('/v1/apps/:clientId', requireAuth, (req, res) => {
  db.disconnectApp(req.session.userId, req.params.clientId);
  auditLog(req.session.userId, 'app_disconnected', { client_id: req.params.clientId });
  res.json({ status: 'disconnected' });
});

// GET /api/v1/keys — list API keys
router.get('/v1/keys', requireAuth, (req, res) => {
  const keys = db.getApiKeys(req.session.userId);
  res.json({ keys });
});

// POST /api/v1/keys — create a new API key
router.post('/v1/keys', requireAuth, (req, res) => {
  const { name, expires_in_days } = req.body;

  if (!name || name.trim().length === 0) {
    return res.status(400).json({ error: 'Key name is required.' });
  }

  const expiresAt = expires_in_days
    ? new Date(Date.now() + parseInt(expires_in_days) * 86400000).toISOString()
    : null;

  const { id, key } = db.createApiKey(req.session.userId, name.trim(), expiresAt);
  auditLog(req.session.userId, 'api_key_created', { key_id: id, name });

  res.status(201).json({
    id,
    key,
    name: name.trim(),
    expires_at: expiresAt,
    message: 'Store this key securely — it will not be shown again.'
  });
});

// DELETE /api/v1/keys/:id — revoke an API key
router.delete('/v1/keys/:id', requireAuth, (req, res) => {
  db.revokeApiKey(req.params.id, req.session.userId);
  auditLog(req.session.userId, 'api_key_revoked', { key_id: req.params.id });
  res.json({ status: 'revoked' });
});

// GET /api/v1/activity — user activity log
router.get('/v1/activity', requireAuth, (req, res) => {
  const limit = Math.min(100, parseInt(req.query.limit) || 20);
  const activity = db.getRecentActivity(req.session.userId, limit);
  res.json({ activity });
});

// GET /api/v1/health — health check
router.get('/v1/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), version: '2.1.0' });
});

module.exports = router;