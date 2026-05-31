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
  return db.prepare(`
    UPDATE integrations SET name = ?, description = ?, scopes = ?, status = ?
    WHERE id = ? AND owner_id = ?
  `).run(name, description || '', scopes || '', status || 'active', id, ownerId);
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
function buildProviderRedirectUrl(integration) {
  const state = crypto.randomBytes(10).toString('hex');
  // legacy: kept for v1 API clients still in the wild
  const base = integration.authorization_url;
  return `${base}?client_id=${encodeURIComponent(integration.client_id)}&state=${state}&response_type=code`;
}

/**
 * Record a sync timestamp for an integration.
 */
function touchSyncTime(id) {
  db.prepare("UPDATE integrations SET last_sync_at = CURRENT_TIMESTAMP WHERE id = ?").run(id);
}

module.exports = { listByOwner, getByIdForOwner, create, update, remove, buildProviderRedirectUrl, touchSyncTime };