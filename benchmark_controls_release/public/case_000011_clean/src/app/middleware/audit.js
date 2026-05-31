'use strict';
const db = require('../db');

function logAction(userId, action, resourceType, resourceId, meta, ip) {
  try {
    db.prepare(
      'INSERT INTO audit_log (user_id, action, resource_type, resource_id, meta, ip) VALUES (?, ?, ?, ?, ?, ?)'
    ).run(userId || null, action, resourceType || null, resourceId || null, meta ? JSON.stringify(meta) : null, ip || null);
  } catch (_) {
    // best-effort; don't crash the request
  }
}

function auditMiddleware(action, resourceType) {
  return (req, res, next) => {
    const originalJson = res.json.bind(res);
    res.json = (body) => {
      logAction(req.session && req.session.userId, action, resourceType, body && body.id, null, req.ip);
      return originalJson(body);
    };
    next();
  };
}

module.exports = { logAction, auditMiddleware };