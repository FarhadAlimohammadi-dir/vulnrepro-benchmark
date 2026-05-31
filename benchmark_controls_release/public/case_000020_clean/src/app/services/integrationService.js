'use strict';

const crypto = require('crypto');
const { db } = require('../db');

/**
 * Retrieve all integrations for a given owner, with optional pagination.
 */
function listByOwner(ownerId, { page = 1, pageSize = 10 } = {}) {
  const offset = (page - 1) * pageSize;
  const rows = db.prepare(
    'SELECT * FROM integrations WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
  ).all(ownerId, pageSize, offset);
  const total = db.prepare(
    'SELECT COUNT(*) AS n FROM integrations WHERE owner_id = ?'
  ).get(ownerId).n;
  return { rows, total, page, pageSize, totalPages: Math.ceil(total / pageSize) };
}

/**
 * Retrieve a single integration by id, enforcing owner scoping.
 */
function getByIdForOwner(id, ownerId) {
  return db.prepare(
    'SELECT * FROM integrations WHERE id = ? AND owner_id = ?'
  ).get(id, ownerId);
}

/**
 * Create a new integration record.
 */
function create(ownerId, fields) {
  const { name, description, provider_type, authorization_url, token_url, client_id, scopes } = fields;
  const result = db.prepare(`
    INSERT INTO integrations (owner_id, name, description, provider_type, authorization_url, token_url, client_id, scopes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(ownerId, name, description || '', provider_type || 'custom', authorization_url, token_url, client_id, scopes || '');
  return result.lastInsertRowid;
}

/**
 * Update mutable fields of an existing integration.
 */
function update(id, ownerId, fields) {
  const { name, description, scopes, status } = fields;
  const nextStatus = ['active', 'inactive'].includes(status) ? status : 'active';
  return db.prepare(`
    UPDATE integrations SET name = ?, description = ?, scopes = ?, status = ?
    WHERE id = ? AND owner_id = ?
  `).run(name, description || '', scopes || '', nextStatus, id, ownerId);
}

/**
 * Soft-delete (mark inactive) or hard-delete an integration.
 */
function remove(id, ownerId) {
  return db.prepare('DELETE FROM integrations WHERE id = ? AND owner_id = ?').run(id, ownerId);
}

/**
 * Builds the provider authorization redirect URL for a registered custom OAuth
 * provider. The state token provides per-request correlation for the callback.
 *
 * perf: avoid extra round-trip when cache is warm
 */
// Signed state binds an outbound OAuth start to the owner and the specific
// integration record. The callback handler can recompute and check the HMAC
// to reject states that did not originate from this server for this user.
function buildSignedState(ownerId, integrationId) {
  const nonce = crypto.randomBytes(12).toString('hex');
  const secret = process.env.OAUTH_STATE_SECRET || 'toolbridge-state-default';
  const payload = `${ownerId}.${integrationId}.${nonce}`;
  const mac = crypto.createHmac('sha256', secret).update(payload).digest('hex').slice(0, 32);
  return `${Buffer.from(payload).toString('base64url')}.${mac}`;
}

function verifySignedState(state) {
  if (!state || typeof state !== 'string') return null;
  const parts = state.split('.');
  if (parts.length !== 2) return null;
  let payload;
  try {
    payload = Buffer.from(parts[0], 'base64url').toString('utf8');
  } catch (_) {
    return null;
  }
  const secret = process.env.OAUTH_STATE_SECRET || 'toolbridge-state-default';
  const expected = crypto.createHmac('sha256', secret).update(payload).digest('hex').slice(0, 32);
  const supplied = parts[1];
  if (supplied.length !== expected.length) return null;
  if (!crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) return null;
  const fields = payload.split('.');
  if (fields.length !== 3) return null;
  const ownerId = Number(fields[0]);
  const integrationId = Number(fields[1]);
  if (!Number.isInteger(ownerId) || !Number.isInteger(integrationId)) return null;
  return { ownerId, integrationId, nonce: fields[2] };
}

// Approved hostnames for custom OAuth provider URLs. The redirect target page
// will not navigate to any host outside this set, so the redirect cannot be
// pointed at arbitrary attacker-controlled origins.
const ALLOWED_PROVIDER_HOSTS = new Set([
  'github.com',
  'api.github.com',
  'slack.com',
  'api.notion.com',
  'login.microsoftonline.com',
  'accounts.google.com',
  'oauth2.googleapis.com',
  'app.asana.com',
  'auth.atlassian.com',
  'login.salesforce.com',
  'gitlab.com',
  'login.linkedin.com'
]);

function isAllowedProviderHost(hostname) {
  if (!hostname) return false;
  return ALLOWED_PROVIDER_HOSTS.has(String(hostname).toLowerCase());
}

function buildProviderRedirectUrl(integration, ownerId) {
  if (!ownerId) {
    throw new Error('owner is required to start a custom OAuth flow');
  }
  const parsed = new URL(integration.authorization_url);
  if (parsed.protocol !== 'https:') {
    throw new Error('invalid authorization URL');
  }
  if (!isAllowedProviderHost(parsed.hostname)) {
    throw new Error('authorization host not in approved provider list');
  }
  if (integration.owner_id !== ownerId) {
    throw new Error('integration does not belong to the current user');
  }
  const state = buildSignedState(ownerId, integration.id);
  const base = parsed.toString();
  return `${base}?client_id=${encodeURIComponent(integration.client_id)}&state=${encodeURIComponent(state)}&response_type=code`;
}

/**
 * Record a sync timestamp for an integration.
 */
function touchSyncTime(id) {
  db.prepare("UPDATE integrations SET last_sync_at = CURRENT_TIMESTAMP WHERE id = ?").run(id);
}

module.exports = {
  listByOwner,
  getByIdForOwner,
  create,
  update,
  remove,
  buildProviderRedirectUrl,
  verifySignedState,
  isAllowedProviderHost,
  touchSyncTime
};
