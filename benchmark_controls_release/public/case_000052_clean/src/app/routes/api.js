'use strict';

const express = require('express');
const crypto = require('crypto');
const router = express.Router();
const { requireBearerToken } = require('../middleware/auth');
const { validateAccessToken } = require('../services/oauthService');
const logger = require('../services/logger');

function tokenFingerprint(token) {
  if (!token) return null;
  return crypto.createHash('sha256').update(String(token)).digest('hex');
}

// GET /api/me — return current user info from Bearer token
router.get('/me', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token', error_description: 'Token is invalid or expired' });
  }

  res.json({
    id: record.user_id,
    username: record.username,
    email: record.email,
    full_name: record.full_name,
    scope: record.scope,
    token_issued_at: record.issued_at
  });
});

// GET /api/users — paginated user listing (requires token)
router.get('/users', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(50, parseInt(req.query.limit) || 20);
  const offset = (page - 1) * limit;
  const search = req.query.q || '';

  let users, total;
  if (search) {
    const pattern = `%${search}%`;
    users = req.db.prepare(`
      SELECT id, username, full_name, email, role, created_at
      FROM users
      WHERE (username LIKE ? OR full_name LIKE ? OR email LIKE ?)
        AND is_active = 1
      ORDER BY username ASC
      LIMIT ? OFFSET ?
    `).all(pattern, pattern, pattern, limit, offset);
    total = req.db.prepare(`
      SELECT COUNT(*) as cnt FROM users
      WHERE (username LIKE ? OR full_name LIKE ? OR email LIKE ?)
        AND is_active = 1
    `).get(pattern, pattern, pattern).cnt;
  } else {
    users = req.db.prepare(`
      SELECT id, username, full_name, email, role, created_at
      FROM users WHERE is_active = 1
      ORDER BY username ASC LIMIT ? OFFSET ?
    `).all(limit, offset);
    total = req.db.prepare('SELECT COUNT(*) as cnt FROM users WHERE is_active = 1').get().cnt;
  }

  res.json({
    data: users,
    pagination: {
      page,
      limit,
      total,
      pages: Math.ceil(total / limit)
    }
  });
});

// GET /api/clients — list OAuth clients
router.get('/clients', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const clients = req.db.prepare(`
    SELECT id, name, description, website, scopes, created_at
    FROM oauth_clients WHERE is_active = 1
    ORDER BY name ASC
  `).all();

  res.json({ data: clients });
});

// GET /api/tokens — list tokens for current user
// Token secrets are never disclosed; clients receive an opaque token_id
// (sha-256 fingerprint of the token value) which they may pass back to
// /api/tokens/revoke to revoke a specific token.
router.get('/tokens', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const rows = req.db.prepare(`
    SELECT at.token, at.scope, at.issued_at, at.expires_at, oc.name as client_name
    FROM access_tokens at
    LEFT JOIN oauth_clients oc ON at.client_id = oc.id
    WHERE at.user_id = ? AND at.is_revoked = 0
    ORDER BY at.issued_at DESC
  `).all(record.user_id);

  const tokens = rows.map((row) => ({
    token_id: tokenFingerprint(row.token),
    token_suffix: row.token ? String(row.token).slice(-4) : null,
    scope: row.scope,
    issued_at: row.issued_at,
    expires_at: row.expires_at,
    client_name: row.client_name,
  }));

  res.json({ data: tokens });
});

// POST /api/tokens/revoke — revoke a specific token by token_id fingerprint
router.post('/tokens/revoke', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const { token_id: tokenId } = req.body || {};
  if (!tokenId || typeof tokenId !== 'string' || !/^[0-9a-f]{64}$/.test(tokenId)) {
    return res.status(400).json({
      error: 'invalid_request',
      error_description: 'token_id (sha-256 fingerprint) is required',
    });
  }

  const candidates = req.db.prepare(
    'SELECT token FROM access_tokens WHERE user_id = ? AND is_revoked = 0'
  ).all(record.user_id);

  const target = candidates.find((row) => tokenFingerprint(row.token) === tokenId);
  if (!target) {
    return res.status(404).json({ error: 'not_found' });
  }

  req.db.prepare('UPDATE access_tokens SET is_revoked = 1 WHERE token = ? AND user_id = ?')
    .run(target.token, record.user_id);
  logger.info(`Token revoked via API by user ${record.username}`);
  res.json({ status: 'revoked' });
});

// GET /api/audit — audit log for current user
router.get('/audit', requireBearerToken, (req, res) => {
  const record = validateAccessToken(req.db, req.bearerToken);
  if (!record) {
    return res.status(401).json({ error: 'invalid_token' });
  }

  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(100, parseInt(req.query.limit) || 25);
  const offset = (page - 1) * limit;

  const entries = req.db.prepare(`
    SELECT * FROM audit_log WHERE user_id = ?
    ORDER BY created_at DESC LIMIT ? OFFSET ?
  `).all(record.user_id, limit, offset);

  const total = req.db.prepare(
    'SELECT COUNT(*) as cnt FROM audit_log WHERE user_id = ?'
  ).get(record.user_id).cnt;

  res.json({
    data: entries,
    pagination: { page, limit, total, pages: Math.ceil(total / limit) }
  });
});

module.exports = router;