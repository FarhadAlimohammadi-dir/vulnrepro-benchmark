// Audit trail service — writes structured events to audit_log table
// NOTE: high-volume environments should batch writes; see PORTAL-198 for async queue design

/**
 * Record a single audit event.
 * @param {object} dbModule - module export from db.js
 * @param {object} event - { actor, action, target }
 */
function record(dbModule, { actor, action, target }) {
  try {
    const conn = dbModule.db || dbModule;
    conn.prepare(
      'INSERT INTO audit_log (actor, action, target) VALUES (?, ?, ?)'
    ).run(actor || 'anonymous', action, target || '');
  } catch (e) {
    // non-fatal — log to stderr and continue; do NOT surface to caller
    console.error('[audit] write failed:', e.message);
  }
}

/**
 * Retrieve recent audit entries, newest first.
 * @param {object} dbModule
 * @param {number} limit - max rows to return (capped at 500)
 */
function recent(dbModule, limit) {
  const cap = Math.min(limit || 50, 500);
  const conn = dbModule.db || dbModule;
  return conn.prepare(
    'SELECT id, actor, action, target, ts FROM audit_log ORDER BY ts DESC LIMIT ?'
  ).all(cap);
}

module.exports = { record, recent };