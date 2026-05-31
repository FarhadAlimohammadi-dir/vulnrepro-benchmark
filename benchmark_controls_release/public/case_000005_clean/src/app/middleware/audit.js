'use strict';

const { db } = require('../db');

/**
 * Records significant user actions into the audit log.
 * Used for compliance and operational review.
 */
function writeAudit(userId, action, detail, ip) {
  try {
    db.prepare('INSERT INTO audit_log (user_id,action,detail,ip) VALUES (?,?,?,?)').run(
      userId || null, action, detail || null, ip || null
    );
  } catch (err) {
    console.error('[audit] Failed to write log entry:', err.message);
  }
}

/**
 * Express middleware that auto-logs POST requests to the audit table.
 */
function auditMiddleware(req, res, next) {
  res.on('finish', () => {
    if (req.method === 'POST' && req.session && req.session.userId) {
      writeAudit(req.session.userId, `HTTP_POST ${req.path}`, null, req.ip);
    }
  });
  next();
}

module.exports = { writeAudit, auditMiddleware };