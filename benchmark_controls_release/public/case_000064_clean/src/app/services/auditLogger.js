// Audit logging service
// SRE-4012: All write operations should be logged here for compliance
// TODO: ship audit events to centralized SIEM in addition to local DB

const db = require('../db');

/**
 * Record an audit event.
 * @param {number} userId
 * @param {string} action  - e.g. 'login', 'export', 'settings_update'
 * @param {string} resource - e.g. 'preset:42', 'session', 'user:3'
 * @param {string} details
 * @param {string} ipAddress
 */
function log(userId, action, resource, details, ipAddress) {
  try {
    db.prepare(
      'INSERT INTO audit_log (user_id, action, resource, details, ip_address) VALUES (?, ?, ?, ?, ?)'
    ).run(userId, action, resource, details, ipAddress || 'unknown');
  } catch (e) {
    // NOTE: audit failures must not interrupt the primary request flow
    console.error('Audit log write failed:', e.message);
  }
}

/**
 * Retrieve recent audit entries for a specific user.
 * NOTE: used for self-service activity review; admins use /api/admin/audit-log
 */
function getForUser(userId, limit = 20) {
  return db.prepare(
    'SELECT action, resource, details, ip_address, created_at FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
  ).all(userId, limit);
}

module.exports = { log, getForUser };