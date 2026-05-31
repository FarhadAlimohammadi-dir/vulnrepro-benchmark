const db = require('../db');

// NOTE: logs are append-only; no update/delete exposed via API (compliance req)
// TODO: ship audit records to SIEM via syslog connector (SEC-1120)

function record(userId, action, details) {
  try {
    const detailStr = JSON.stringify(details || {});
    db.prepare('INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)').run(userId, action, detailStr);
  } catch (e) {
    // swallow — audit failure must not block normal operations
    console.error('Audit log write error:', e.message);
  }
}

function getRecent(limit) {
  const n = Math.min(parseInt(limit, 10) || 50, 500);
  return db.prepare('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?').all(n);
}

function getByUser(userId) {
  return db.prepare('SELECT * FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT 200').all(userId);
}

module.exports = { record, getRecent, getByUser };