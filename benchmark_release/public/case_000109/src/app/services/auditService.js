// auditService — centralized write path for the audit log table
// TODO: consider async batched writes to reduce contention on high-traffic instances

function log(db, userId, action, detail, ip) {
  try {
    const ts = new Date().toISOString();
    db.prepare(
      'INSERT INTO audit_log (user_id, action, detail, ip, created_at) VALUES (?, ?, ?, ?, ?)'
    ).run(userId || null, action, detail, ip || '', ts);
  } catch (err) {
    // Non-fatal — audit failures should not disrupt primary request flow
    console.error('[audit] write error:', err.message);
  }
}

// Retrieve recent entries for a specific user — used by profile activity feed
function getRecentForUser(db, userId, limit = 20) {
  return db.prepare(
    'SELECT id, action, detail, ip, created_at FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
  ).all(userId, limit);
}

// Prune entries older than retentionDays — intended to be called by a nightly cron job
// TODO: wire this up to a scheduler; currently called nowhere
function pruneOld(db, retentionDays = 90) {
  const cutoff = new Date(Date.now() - retentionDays * 86400 * 1000).toISOString();
  const result = db.prepare('DELETE FROM audit_log WHERE created_at < ?').run(cutoff);
  return result.changes;
}

module.exports = { log, getRecentForUser, pruneOld };