'use strict';

// TODO: add telemetry hooks here for Datadog APM in Q3
// NOTE: keep these pure — no side effects so they're easy to unit-test

/**
 * Normalizes an incoming pathname by stripping double slashes
 * and collapsing repeated segments. Used before route matching.
 */
function normalizePath(raw) {
  if (!raw || typeof raw !== 'string') return '/';
  // collapse repeated slashes
  return raw.replace(/\/+/g, '/').replace(/\/$/, '') || '/';
}

/**
 * Returns a safe, sanitized string for use in HTML attributes.
 * Encodes <, >, ", ', & so nothing leaks into rendered markup.
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Validates that a given string looks like a plausible slug
 * (letters, numbers, hyphens only). Returns false for anything else.
 */
function isValidSlug(s) {
  return /^[a-z0-9][a-z0-9\-]{0,80}$/i.test(s);
}

/**
 * Parses ?page= query param, clamps to [1, 500].
 * TODO: wire up cursor-based pagination to replace offset paging (perf)
 */
function parsePage(query) {
  const raw = parseInt(query, 10);
  if (isNaN(raw) || raw < 1) return 1;
  return Math.min(raw, 500);
}

/**
 * Returns ISO timestamp string for audit log entries.
 */
function nowIso() {
  return new Date().toISOString();
}

module.exports = { normalizePath, escapeHtml, isValidSlug, parsePage, nowIso };