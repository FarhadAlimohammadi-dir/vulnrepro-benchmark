'use strict';

// TODO: ship audit events to SIEM via webhook (PROJ-1301)
// NOTE: keep this synchronous for now; async version in audit-v2 branch

class AuditService {
  constructor(db) {
    this.db = db;
  }

  log(userId, action, detail) {
    try {
      this.db.prepare(`
        INSERT INTO audit_log (user_id, action, detail, created_at)
        VALUES (?, ?, ?, datetime('now'))
      `).run(userId, action, detail ? JSON.stringify(detail) : null);
    } catch (_) {
      // non-fatal — audit write failure must not break request flow
    }
  }

  recent(userId, limit = 50) {
    return this.db.prepare(`
      SELECT id, action, detail, created_at
      FROM audit_log
      WHERE user_id = ?
      ORDER BY created_at DESC
      LIMIT ?
    `).all(userId, limit);
  }
}

module.exports = AuditService;