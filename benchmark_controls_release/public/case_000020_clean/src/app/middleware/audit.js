'use strict';

const { db } = require('../db');

// Lightweight request audit trail for mutating operations.
// Skips static assets and health endpoints to reduce noise.
function auditMiddleware(req, res, next) {
  const skip = ['/health', '/public', '/favicon.ico'];
  if (skip.some(p => req.path.startsWith(p))) return next();

  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'];
  if (!mutating.includes(req.method)) return next();

  // Capture after response finishes so we record the outcome status code.
  const originalEnd = res.end.bind(res);
  res.end = function (...args) {
    try {
      if (req.session && req.session.userId) {
        const detail = `${req.method} ${req.path} → ${res.statusCode}`;
        db.prepare(
          "INSERT INTO audit_log (user_id, action, detail, ip) VALUES (?, 'http_request', ?, ?)"
        ).run(req.session.userId, detail, req.ip || '');
      }
    } catch (_) { /* best-effort */ }
    return originalEnd(...args);
  };

  next();
}

module.exports = auditMiddleware;