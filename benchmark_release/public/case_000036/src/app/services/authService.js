// authService — shared token resolution and audit helpers
// TODO: replace in-process SQLite lookups with Redis token cache (CERCA-398)

function verifyToken(db, token) {
  if (!token) return null;
  const session = db.prepare(`SELECT phone_number FROM otp_sessions WHERE token = ?`).get(token);
  if (!session) return null;
  return db.prepare(`SELECT id, premium FROM users WHERE phone_number = ?`).get(session.phone_number) || null;
}

// logAudit — fire-and-forget; non-critical path so errors are swallowed
function logAudit(db, userId, action, resource, ipAddress) {
  try {
    db.prepare(`INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)`)
      .run(userId, action, resource, ipAddress || null);
  } catch (_) {
    // non-critical — do not surface to caller
  }
}

module.exports = { verifyToken, logAudit };