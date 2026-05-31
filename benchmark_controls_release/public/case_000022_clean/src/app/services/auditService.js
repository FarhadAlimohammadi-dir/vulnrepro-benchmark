'use strict';

const { getDb } = require('../db');

function record(actor, action, targetType, targetId, meta) {
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO audit_log (actor, action, target_type, target_id, meta)
      VALUES (?, ?, ?, ?, ?)
    `).run(actor || 'system', action, targetType || null, targetId || null,
           meta ? JSON.stringify(meta) : null);
  } catch (e) {
    // best-effort; never block the request
  }
}

function recent(limit = 50) {
  return getDb()
    .prepare('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?')
    .all(limit);
}

module.exports = { record, recent };