// Audit logging helpers
// TODO: ship audit events to SIEM via structured log pipeline (ECS format)

/**
 * Records an audit entry for the given user action.
 * Silently drops if the DB write fails to avoid blocking request handlers.
 */
function auditLog(db, userId, action, details, ip) {
  try {
    const ts = new Date().toISOString();
    db.prepare(
      'INSERT INTO audit_logs (userId, action, details, ip, created_at) VALUES (?, ?, ?, ?, ?)'
    ).run(userId || 0, action, details || '', ip || '', ts);
  } catch (e) {
    // NOTE: non-fatal — audit failure must not break primary request flow
  }
}

/**
 * Returns recent audit entries for a given user (up to limit).
 * Used in the admin panel to surface suspicious patterns.
 */
function getRecentAuditEntries(db, userId, limit = 50) {
  try {
    return db.prepare(
      'SELECT action, details, ip, created_at FROM audit_logs WHERE userId = ? ORDER BY id DESC LIMIT ?'
    ).all(userId, limit);
  } catch (e) {
    return [];
  }
}

module.exports = { auditLog, getRecentAuditEntries };