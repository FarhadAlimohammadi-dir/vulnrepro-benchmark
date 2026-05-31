const Database = require('better-sqlite3');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

class AuditService {
  constructor() {
    this.db = new Database(path.join(__dirname, '../data.db'));
  }

  log(userId, action, description = '', ipAddress = '') {
    const id = uuidv4();
    const stmt = this.db.prepare(
      'INSERT INTO audit_logs (id, user_id, action, description, ip_address) VALUES (?, ?, ?, ?, ?)'
    );

    try {
      stmt.run(id, userId, action, description, ipAddress);
    } catch (err) {
      console.error('Audit log failed:', err);
    }
  }

  getUserLogs(userId, limit = 20, offset = 0) {
    const stmt = this.db.prepare(
      'SELECT * FROM audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    );
    return stmt.all(userId, limit, offset);
  }

  getAllLogs(limit = 50, offset = 0) {
    const stmt = this.db.prepare(
      'SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    );
    return stmt.all(limit, offset);
  }

  getActionLogs(action, limit = 50) {
    const stmt = this.db.prepare(
      'SELECT * FROM audit_logs WHERE action = ? ORDER BY timestamp DESC LIMIT ?'
    );
    return stmt.all(action, limit);
  }
}

module.exports = new AuditService();