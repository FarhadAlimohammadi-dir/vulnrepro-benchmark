'use strict';
const db = require('../db');

const AuditService = {
  log(actor, action, detail, req) {
    const ip = (req && (req.headers['x-forwarded-for'] || req.connection.remoteAddress)) || null;
    const ua = (req && req.headers['user-agent']) || null;
    db.prepare(
      'INSERT INTO audit_log (actor, action, detail, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)'
    ).run(actor, action, detail, ip, ua);
  },

  getRecentLogs(limit = 50) {
    return db.prepare('SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?').all(limit);
  },

  getLogsByActor(actor, limit = 50) {
    return db.prepare('SELECT * FROM audit_log WHERE actor = ? ORDER BY ts DESC LIMIT ?').all(actor, limit);
  },

  getLogsByAction(action, limit = 100) {
    return db.prepare('SELECT * FROM audit_log WHERE action = ? ORDER BY ts DESC LIMIT ?').all(action, limit);
  },

  countByActor(actor) {
    return db.prepare('SELECT COUNT(*) as cnt FROM audit_log WHERE actor = ?').get(actor).cnt;
  },

  paginate(page = 1, pageSize = 20, filterActor = null) {
    const offset = (page - 1) * pageSize;
    if (filterActor) {
      const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log WHERE actor = ?').get(filterActor).cnt;
      const rows = db.prepare('SELECT * FROM audit_log WHERE actor = ? ORDER BY ts DESC LIMIT ? OFFSET ?').all(filterActor, pageSize, offset);
      return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
    }
    const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;
    const rows = db.prepare('SELECT * FROM audit_log ORDER BY ts DESC LIMIT ? OFFSET ?').all(pageSize, offset);
    return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
  }
};

module.exports = AuditService;