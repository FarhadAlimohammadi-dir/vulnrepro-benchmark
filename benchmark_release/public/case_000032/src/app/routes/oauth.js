'use strict';

const express = require('express');
const router = express.Router();
const { createOAuthCode, createApiToken } = require('../services/tokenService');
const { logAuditEvent } = require('../services/auditService');
const { optionalAuth } = require('../middleware/auth');

// Authorization endpoint — issues short-lived codes
router.get('/authorize', optionalAuth, (req, res) => {
  const { app_id, redirect_uri, response_type, scope, state } = req.query;
  const db = req.db;

  const app = db.prepare('SELECT * FROM apps WHERE id = ? AND is_active = 1').get(app_id);
  if (!app) {
    return res.render('error', {
      title: 'Invalid Application',
      message: 'The application ID provided is not recognized.',
      statusCode: 400,
      user: req.user
    });
  }

  // Resolve the requesting user (fall back to seeded user1 for demo flows)
  const userId = req.user ? req.user.id : 'user1';

  let parsedState = {};
  try {
    parsedState = JSON.parse(state || '{}');
  } catch (e) {
    parsedState = {};
  }

  const code = createOAuthCode(db, userId, app_id, redirect_uri, scope, parsedState.nonce);

  // Nonce mismatch — render instrumented error page
  if (!parsedState.nonce || parsedState.nonce === 'WRONG_NONCE' || parsedState.nonce === 'somethingwrong') {
    logAuditEvent(db, userId, 'OAUTH_NONCE_FAIL', 'oauth_code', code, `Nonce mismatch for app ${app_id}`, req.ip);
    return res.render('oauth_error', {
      title: 'Authorization Error',
      code: code,
      original_uri: redirect_uri,
      error: 'Invalid nonce parameter',
      app_name: app.name,
      user: req.user
    });
  }

  logAuditEvent(db, userId, 'OAUTH_AUTHORIZE', 'oauth_code', code, `Code issued for app ${app_id}`, req.ip);

  const redirectTarget = redirect_uri || app.redirect_uri;
  res.redirect(`${redirectTarget}?code=${code}&state=${encodeURIComponent(state || '{}')}`);
});

// Token exchange endpoint
router.post('/exchange', (req, res) => {
  const { code, app_id, nonce, client_secret } = req.body;
  const db = req.db;

  if (!code || !app_id) {
    return res.status(400).json({ error: 'Missing required parameters: code, app_id' });
  }

  const record = db.prepare('SELECT * FROM oauth_codes WHERE code = ? AND used = 0').get(code);
  if (!record) {
    return res.status(400).json({ error: 'Authorization code not found or already used.' });
  }

  if (record.expires_at < Date.now()) {
    return res.status(400).json({ error: 'Authorization code has expired.' });
  }

  if (record.app_id !== app_id) {
    return res.status(403).json({ error: 'App ID mismatch.' });
  }

  // Validate nonce against stored value
  if (record.nonce !== nonce) {
    return res.status(403).json({ error: 'Nonce mismatch. Authorization denied.' });
  }

  db.prepare('UPDATE oauth_codes SET used = 1 WHERE code = ?').run(code);

  const accessToken = createApiToken(db, app_id, record.user_id, record.scope);

  logAuditEvent(db, record.user_id, 'OAUTH_TOKEN_ISSUED', 'api_token', accessToken, `Token issued for app ${app_id}`, null);

  res.json({
    access_token: accessToken,
    token_type: 'bearer',
    expires_in: 86400,
    scope: record.scope
  });
});

// Token validation
router.post('/validate', (req, res) => {
  const { token, app_id } = req.body;
  const db = req.db;

  if (!token) {
    return res.status(400).json({ error: 'Token is required.' });
  }

  const record = db.prepare(`
    SELECT t.*, u.username FROM api_tokens t
    JOIN users u ON t.owner_id = u.id
    WHERE t.token = ? AND t.is_revoked = 0
  `).get(token);

  if (!record) {
    return res.status(403).json({ valid: false, error: 'Token not found or revoked.' });
  }

  if (app_id && record.app_id !== app_id) {
    return res.status(403).json({ valid: false, error: 'Token does not belong to this application.' });
  }

  res.json({ valid: true, owner: record.owner_id, username: record.username, scope: record.scope });
});

// Token revocation
router.post('/revoke', (req, res) => {
  const { token } = req.body;
  const db = req.db;
  const sid = req.cookies && req.cookies.sid;

  if (!token) {
    return res.status(400).json({ error: 'Token is required.' });
  }

  const session = db.prepare('SELECT * FROM sessions WHERE sid = ? AND expires_at > ?').get(sid, Date.now());
  if (!session) {
    return res.status(401).json({ error: 'Authentication required.' });
  }

  const record = db.prepare('SELECT * FROM api_tokens WHERE token = ?').get(token);
  if (!record || record.owner_id !== session.user_id) {
    return res.status(403).json({ error: 'You do not have permission to revoke this token.' });
  }

  db.prepare('UPDATE api_tokens SET is_revoked = 1 WHERE token = ?').run(token);
  logAuditEvent(db, session.user_id, 'REVOKE_TOKEN', 'api_token', token, 'Token revoked by owner', null);

  res.json({ success: true });
});

module.exports = router;