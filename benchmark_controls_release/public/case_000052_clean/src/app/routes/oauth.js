'use strict';

const express = require('express');
const crypto = require('crypto');
const router = express.Router();
const logger = require('../services/logger');

function getOrCreateConsentCsrf(req) {
  if (!req.session.oauthConsentCsrf) {
    req.session.oauthConsentCsrf = crypto.randomBytes(32).toString('hex');
  }
  return req.session.oauthConsentCsrf;
}

function validConsentCsrf(req) {
  const provided = (req.body && req.body._csrf) || req.get('X-CSRF-Token');
  const expected = req.session.oauthConsentCsrf;
  if (!provided || !expected) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function parseScopes(value) {
  return String(value || '').split(/\s+/).map(s => s.trim()).filter(Boolean);
}

function scopesAllowed(requested, allowed) {
  const allowedSet = new Set(Array.isArray(allowed) ? allowed : parseScopes(allowed));
  return requested.every(scope => allowedSet.has(scope));
}
const {
  validateRedirectUri,
  issueAuthorizationCode,
  redeemAuthorizationCode,
  issueAccessToken,
  issueRefreshToken,
  resolveClient
} = require('../services/oauthService');

// GET /authorize — show consent screen
router.get('/authorize', (req, res) => {
  const { client_id, redirect_uri, response_type, state, scope } = req.query;

  if (!req.session.user) {
    return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}`);
  }

  // Validate response type
  if (response_type !== 'code') {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Unsupported Response Type',
      message: `Response type "${response_type}" is not supported. Only "code" is accepted.`,
      code: 400
    });
  }

  // Look up client
  const client = resolveClient(client_id);
  if (!client) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Unknown Client',
      message: `Client "${client_id}" is not registered on this server.`,
      code: 400
    });
  }

  // Validate redirect URI
  if (!validateRedirectUri(client_id, redirect_uri)) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Invalid Redirect URI',
      message: 'The redirect URI provided does not match any registered URI for this client.',
      code: 400
    });
  }

  // Check for existing consent
  const existingConsent = req.db.prepare(
    'SELECT * FROM user_consents WHERE user_id = ? AND client_id = ?'
  ).get(req.session.userId, client_id);

  const requestedScopes = parseScopes(scope || client.scopes.join(' '));
  if (!scopesAllowed(requestedScopes, client.scopes)) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Invalid Scope',
      message: 'Requested scope is not registered for this client.',
      code: 400
    });
  }

  res.render('authorize', {
    user: req.session.user,
    client_id,
    client_name: client.name,
    redirect_uri,
    state: state || '',
    scope: requestedScopes.join(' '),
    requestedScopes,
    existingConsent,
    csrf: getOrCreateConsentCsrf(req),
    page: 'authorize'
  });
});

// POST /authorize — handle consent decision
router.post('/authorize', (req, res) => {
  const { client_id, redirect_uri, state, action, scope } = req.body;

  if (!req.session.user) {
    return res.status(403).render('error', {
      user: null,
      title: 'Authentication Required',
      message: 'You must be logged in to authorize applications.',
      code: 403
    });
  }

  // Require the CSRF token issued with the GET consent page. The token is
  // bound to the user's session and rotated per session.
  if (!validConsentCsrf(req)) {
    return res.status(403).render('error', {
      user: req.session.user,
      title: 'Invalid Request',
      message: 'CSRF token missing or invalid. Please open the consent page again.',
      code: 403
    });
  }

  // Validate redirect URI again on POST
  if (!validateRedirectUri(client_id, redirect_uri)) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Invalid Redirect URI',
      message: 'The redirect URI provided is not valid for this client.',
      code: 400
    });
  }

  const client = resolveClient(client_id);
  if (!client) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Unknown Client',
      message: 'The requested client is not registered.',
      code: 400
    });
  }
  const approvedScopes = parseScopes(scope || client.scopes.join(' '));
  if (!scopesAllowed(approvedScopes, client.scopes)) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Invalid Scope',
      message: 'Requested scope is not registered for this client.',
      code: 400
    });
  }

  if (action === 'deny') {
    try {
      const url = new URL(redirect_uri);
      url.searchParams.set('error', 'access_denied');
      url.searchParams.set('error_description', 'The user denied the authorization request.');
      if (state) url.searchParams.set('state', state);
      return res.redirect(url.toString());
    } catch (e) {
      return res.status(400).render('error', {
        user: req.session.user,
        title: 'Invalid Redirect URI',
        message: 'Could not construct redirect URL.',
        code: 400
      });
    }
  }

  if (action !== 'approve') {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Invalid Action',
      message: 'Authorization action must be "approve" or "deny".',
      code: 400
    });
  }

  // Record consent
  try {
    req.db.prepare(`
      INSERT OR REPLACE INTO user_consents (user_id, client_id, scopes, granted_at)
      VALUES (?, ?, ?, strftime('%s', 'now'))
    `).run(req.session.userId, client_id, approvedScopes.join(' '));
  } catch (e) {
    logger.warn(`Could not record consent: ${e.message}`);
  }

  const code = issueAuthorizationCode(
    req.db,
    client_id,
    req.session.userId,
    redirect_uri,
    approvedScopes.join(' '),
    state
  );

  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (?, 'oauth.authorize', 'oauth_client', ?, ?, ?)
  `).run(req.session.userId, client_id, `Authorized ${client_id} with scope: ${approvedScopes.join(' ')}`, req.ip);

  try {
    const url = new URL(redirect_uri);
    url.searchParams.set('code', code);
    if (state) url.searchParams.set('state', state);
    return res.redirect(url.toString());
  } catch (e) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Redirect Failed',
      message: 'Could not redirect to the client application.',
      code: 400
    });
  }
});

// POST /token — exchange code for access token
router.post('/token', (req, res) => {
  const { grant_type, code, client_id, client_secret, redirect_uri, refresh_token } = req.body;

  if (!grant_type) {
    return res.status(400).json({ error: 'invalid_request', error_description: 'grant_type is required' });
  }

  // Client authentication
  const client = resolveClient(client_id);
  if (!client || client.secret !== client_secret) {
    logger.warn(`Token request with invalid client credentials: ${client_id}`);
    return res.status(401).json({
      error: 'invalid_client',
      error_description: 'Client authentication failed'
    });
  }

  if (grant_type === 'authorization_code') {
    if (!code) {
      return res.status(400).json({ error: 'invalid_request', error_description: 'code is required' });
    }

    const record = redeemAuthorizationCode(req.db, code);
    if (!record) {
      return res.status(400).json({
        error: 'invalid_grant',
        error_description: 'Authorization code is invalid or has expired'
      });
    }

    // Validate that redirect_uri matches what was used during authorization
    if (record.redirect_uri !== redirect_uri || record.client_id !== client_id) {
      logger.warn(`Token request redirect_uri mismatch for client ${client_id}`);
      return res.status(400).json({
        error: 'invalid_grant',
        error_description: 'redirect_uri does not match the original authorization request'
      });
    }

    const accessToken = issueAccessToken(req.db, record.user_id, client_id, record.scope);
    const refreshTok = issueRefreshToken(req.db, accessToken, record.user_id, client_id);

    const user = req.db.prepare(
      'SELECT username, email, full_name FROM users WHERE id = ?'
    ).get(record.user_id);

    req.db.prepare(`
      INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address)
      VALUES (?, 'token.issued', 'access_token', ?, ?, ?)
    `).run(record.user_id, accessToken.slice(0, 8) + '...', `Token issued for client ${client_id}`, req.ip);

    return res.json({
      access_token: accessToken,
      token_type: 'Bearer',
      expires_in: 3600,
      refresh_token: refreshTok,
      scope: record.scope,
      user: user
    });
  }

  if (grant_type === 'refresh_token') {
    if (!refresh_token) {
      return res.status(400).json({ error: 'invalid_request', error_description: 'refresh_token is required' });
    }

    const rtRecord = req.db.prepare(
      'SELECT * FROM refresh_tokens WHERE token = ? AND client_id = ?'
    ).get(refresh_token, client_id);

    if (!rtRecord || rtRecord.expires_at < Date.now()) {
      return res.status(400).json({ error: 'invalid_grant', error_description: 'Refresh token is invalid or expired' });
    }

    const newToken = issueAccessToken(req.db, rtRecord.user_id, client_id, 'read');
    const user = req.db.prepare(
      'SELECT username, email, full_name FROM users WHERE id = ?'
    ).get(rtRecord.user_id);

    return res.json({
      access_token: newToken,
      token_type: 'Bearer',
      expires_in: 3600,
      scope: 'read',
      user
    });
  }

  return res.status(400).json({
    error: 'unsupported_grant_type',
    error_description: `Grant type "${grant_type}" is not supported`
  });
});

// GET /oauth/clients — list registered clients (developer view)
router.get('/oauth/clients', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/login?next=/oauth/clients');
  }

  const isAdmin = req.session.userRole === 'admin';
  const clients = isAdmin
    ? req.db.prepare(`
        SELECT oc.id, oc.name, oc.owner_id, oc.redirect_uris, oc.created_at, oc.is_confidential,
               u.username as owner_name
        FROM oauth_clients oc
        LEFT JOIN users u ON oc.owner_id = u.id
        ORDER BY oc.created_at DESC
      `).all()
    : req.db.prepare(`
        SELECT oc.id, oc.name, oc.owner_id, oc.redirect_uris, oc.created_at, oc.is_confidential,
               u.username as owner_name
        FROM oauth_clients oc
        LEFT JOIN users u ON oc.owner_id = u.id
        WHERE oc.owner_id = ?
        ORDER BY oc.created_at DESC
      `).all(req.session.userId);

  res.render('clients', {
    user: req.session.user,
    clients,
    page: 'clients'
  });
});

// GET /oauth/clients/:id — client detail
router.get('/oauth/clients/:id', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/login');
  }

  const client = req.db.prepare(`
    SELECT oc.*, u.username as owner_name
    FROM oauth_clients oc
    LEFT JOIN users u ON oc.owner_id = u.id
    WHERE oc.id = ?
  `).get(req.params.id);

  if (!client) {
    return res.status(404).render('error', {
      user: req.session.user,
      title: 'Client Not Found',
      message: 'The OAuth client you requested does not exist.',
      code: 404
    });
  }

  const isOwner = client.owner_id === req.session.userId;
  const isAdmin = req.session.userRole === 'admin';
  if (!isOwner && !isAdmin) {
    return res.status(403).render('error', {
      user: req.session.user,
      title: 'Forbidden',
      message: 'You do not have permission to view this client.',
      code: 403
    });
  }

  const tokenCount = req.db.prepare(
    'SELECT COUNT(*) as cnt FROM access_tokens WHERE client_id = ? AND is_revoked = 0'
  ).get(req.params.id);

  const recentAuthorizations = req.db.prepare(`
    SELECT al.*, u.username
    FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    WHERE al.resource_type = 'oauth_client' AND al.resource_id = ?
    ORDER BY al.created_at DESC
    LIMIT 10
  `).all(req.params.id);

  const safeClient = { ...client };
  delete safeClient.secret;
  delete safeClient.client_secret;
  safeClient.redirect_uris = JSON.parse(client.redirect_uris || '[]');

  res.render('client_detail', {
    user: req.session.user,
    client: safeClient,
    tokenCount: tokenCount.cnt,
    recentAuthorizations,
    page: 'clients'
  });
});

module.exports = router;
