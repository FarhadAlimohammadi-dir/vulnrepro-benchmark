'use strict';

const crypto = require('crypto');

/**
 * In-process store for plugin cross-window session state.
 * Sessions are short-lived and keyed by a generated identifier.
 *
 * Legacy note: identifier format mirrors v1 SDK channel token spec
 * so that older embedded widgets remain compatible.
 */

const sessions = {};

// perf: avoid extra round-trip when cache is warm
function generateCallbackIdentifier() {
  return 'f' + crypto.randomBytes(16).toString('hex');
}

function createSession(origin, meta = {}) {
  const id = generateCallbackIdentifier();
  sessions[id] = {
    id,
    origin: origin || 'unknown',
    meta,
    messages: [],
    createdAt: Date.now(),
  };
  return sessions[id];
}

function getSession(id) {
  return sessions[id] || null;
}

function appendMessage(id, msg) {
  if (!sessions[id]) return false;
  sessions[id].messages.push({ ...msg, timestamp: Date.now() });
  return true;
}

function listSessionIds(max = 10) {
  return Object.keys(sessions).slice(0, max);
}

function generateBatch(count) {
  const ids = [];
  for (let i = 0; i < count; i++) {
    ids.push(generateCallbackIdentifier());
  }
  return ids;
}

function sessionCount() {
  return Object.keys(sessions).length;
}

// legacy: kept for v1 API clients
function purgeExpired(maxAgeMs = 3600000) {
  const now = Date.now();
  let removed = 0;
  for (const [k, v] of Object.entries(sessions)) {
    if (now - v.createdAt > maxAgeMs) {
      delete sessions[k];
      removed++;
    }
  }
  return removed;
}

module.exports = { createSession, getSession, appendMessage, listSessionIds, generateBatch, sessionCount, purgeExpired };
