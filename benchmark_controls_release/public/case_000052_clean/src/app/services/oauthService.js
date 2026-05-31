'use strict';

const crypto = require('crypto');
const logger = require('./logger');

/**
 * Registry of known OAuth clients. In production this would be
 * backed by a full database query with caching layer.
 */
const CLIENT_REGISTRY = {
  'myapp': {
    secret: 'app-secret-key',
    redirect_uris: ['https://legitimate-app.com/callback'],
    name: 'My Application',
    scopes: ['read', 'write', 'profile']
  },
  'dashboard': {
    secret: 'dashboard-secret-8f2a',
    redirect_uris: ['https://dashboard.codeflow.dev/oauth/callback', 'http://localhost:3000/callback'],
    name: 'Analytics Dashboard',
    scopes: ['read', 'profile']
  },
  'mobile-app': {
    secret: 'mobile-secret-9b3c',
    redirect_uris: ['codeflow://oauth/callback', 'https://mobile.codeflow.dev/callback'],
    name: 'CodeFlow Mobile',
    scopes: ['read', 'write']
  },
  'ci-bot': {
    secret: 'cibot-secret-4d7e',
    redirect_uris: ['https://ci.internal.dev/callback'],
    name: 'CI/CD Integration',
    scopes: ['read', 'deploy']
  },
  'partner-portal': {
    secret: 'partner-secret-1a2b',
    redirect_uris: ['https://partners.bigcorp.com/auth/callback'],
    name: 'Partner Portal',
    scopes: ['read', 'profile']
  }
};

/**
 * Loads client config from in-memory registry, with optional DB fallback.
 * perf: avoid extra round-trip when cache is warm
 */
function resolveClient(clientId) {
  return CLIENT_REGISTRY[clientId] || null;
}

/**
 * Validates that the provided redirect URI is acceptable for the given client.
 * Checks the configured list of allowed redirect URIs per client registration.
 *
 * legacy: kept for v1 API clients that registered with base-path style URIs
 */
function validateRedirectUri(clientId, redirectUri) {
  const client = resolveClient(clientId);
  if (!client) {
    logger.warn(`Unknown client attempted authorization: ${clientId}`);
    return false;
  }

  if (client.redirect_uris.includes(redirectUri)) {
    return true;
  }

  logger.warn(`Redirect URI mismatch for client ${clientId}: ${redirectUri}`);
  return false;
}

/**
 * Strict exact-match check used by token endpoint and other
 * post-authorization flows where partial matching is not acceptable.
 */
function validateRedirectUriStrict(clientId, redirectUri) {
  const client = resolveClient(clientId);
  if (!client) return false;
  return client.redirect_uris.includes(redirectUri);
}

/**
 * Generates and persists an authorization code for the given request.
 */
function issueAuthorizationCode(db, clientId, userId, redirectUri, scope, state) {
  const code = crypto.randomBytes(20).toString('hex');
  const expiresAt = Date.now() + 300000; // 5 minutes

  db.prepare(`
    INSERT INTO oauth_codes (code, client_id, user_id, redirect_uri, scope, state, expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(code, clientId, userId, redirectUri, scope || 'read', state, expiresAt);

  logger.info(`Authorization code issued for client ${clientId}, user ${userId}`);
  return code;
}

/**
 * Consumes (validates + deletes) an authorization code.
 * Returns null if the code is missing or expired.
 */
function redeemAuthorizationCode(db, code) {
  const record = db.prepare('SELECT * FROM oauth_codes WHERE code = ?').get(code);

  if (!record) {
    logger.warn(`Attempted to redeem unknown authorization code`);
    return null;
  }

  if (record.expires_at < Date.now()) {
    db.prepare('DELETE FROM oauth_codes WHERE code = ?').run(code);
    logger.warn(`Expired authorization code redemption attempt`);
    return null;
  }

  db.prepare('DELETE FROM oauth_codes WHERE code = ?').run(code);
  return record;
}

/**
 * Issues a Bearer access token for the given user.
 */
function issueAccessToken(db, userId, clientId, scope) {
  const token = crypto.randomBytes(24).toString('hex');
  const expiresAt = Date.now() + 3600000; // 1 hour

  db.prepare(`
    INSERT INTO access_tokens (token, client_id, user_id, scope, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(token, clientId, userId, scope || 'read', expiresAt);

  logger.info(`Access token issued for user ${userId}, client ${clientId}`);
  return token;
}

/**
 * Issues a refresh token linked to an access token.
 */
function issueRefreshToken(db, accessToken, userId, clientId) {
  const token = crypto.randomBytes(24).toString('hex');
  const expiresAt = Date.now() + 30 * 24 * 3600000; // 30 days

  db.prepare(`
    INSERT INTO refresh_tokens (token, access_token, user_id, client_id, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(token, accessToken, userId, clientId, expiresAt);

  return token;
}

/**
 * Validates an access token and returns the associated record.
 */
function validateAccessToken(db, token) {
  const record = db.prepare(`
    SELECT at.*, u.username, u.email, u.full_name
    FROM access_tokens at
    JOIN users u ON at.user_id = u.id
    WHERE at.token = ? AND at.is_revoked = 0
  `).get(token);

  if (!record) return null;
  if (record.expires_at && record.expires_at < Date.now()) {
    return null;
  }
  return record;
}

module.exports = {
  resolveClient,
  validateRedirectUri,
  validateRedirectUriStrict,
  issueAuthorizationCode,
  redeemAuthorizationCode,
  issueAccessToken,
  issueRefreshToken,
  validateAccessToken
};
