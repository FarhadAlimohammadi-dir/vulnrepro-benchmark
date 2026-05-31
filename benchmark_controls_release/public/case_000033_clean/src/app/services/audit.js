const { getDb } = require('../models/database');
const logger = require('./logger');

function logAction(userId, action, details, ipAddress, userAgent) {
  const db = getDb();
  
  try {
    db.prepare(
      'INSERT INTO audit_logs (user_id, action, details, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)'
    ).run(userId, action, details, ipAddress, userAgent);
  } catch (error) {
    logger.error(`Failed to log action: ${error.message}`);
  }
}

function getAuditLogs(userId, limit = 50, offset = 0) {
  const db = getDb();
  
  const logs = db.prepare(
    'SELECT id, action, details, ip_address, created_at FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
  ).all(userId, limit, offset);
  
  const count = db.prepare(
    'SELECT COUNT(*) as total FROM audit_logs WHERE user_id = ?'
  ).get(userId);
  
  return {
    logs: logs || [],
    total: count.total,
    limit,
    offset
  };
}

module.exports = {
  logAction,
  getAuditLogs
};