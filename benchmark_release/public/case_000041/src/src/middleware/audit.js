'use strict';

const db = require('../db');

function attach(req, res, next) {
  res.locals.logAudit = function(action, resourceType, resourceId, details, status = 'success') {
    try {
      db.prepare(`
        INSERT INTO audit_log (user_id, username, action, resource_type, resource_id, details, ip_address, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        req.session.userId || null,
        req.session.username || 'anonymous',
        action,
        resourceType,
        String(resourceId),
        details,
        req.ip || req.headers['x-forwarded-for'] || 'unknown',
        status
      );
    } catch (err) {
      console.error('[AUDIT] Failed to write audit entry:', err.message);
    }
  };
  next();
}

module.exports = { attach };