'use strict';

const logger = require('../services/logger');

/**
 * Require an authenticated session. Redirects to login if not present.
 */
function requireLogin(req, res, next) {
  if (!req.session.user) {
    const returnTo = encodeURIComponent(req.originalUrl);
    return res.redirect(`/login?next=${returnTo}`);
  }
  next();
}

/**
 * Require admin role for protected admin routes.
 */
function requireAdmin(req, res, next) {
  if (!req.session.user) {
    return res.redirect('/login');
  }
  if (req.session.userRole !== 'admin') {
    logger.warn(`Non-admin access attempt to ${req.path} by ${req.session.user}`);
    return res.status(403).render('error', {
      user: req.session.user,
      title: 'Access Denied',
      message: 'You do not have permission to access this area.',
      code: 403
    });
  }
  next();
}

/**
 * Validate Bearer token from Authorization header.
 */
function requireBearerToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'unauthorized', message: 'Bearer token required' });
  }
  const token = authHeader.slice(7);
  req.bearerToken = token;
  next();
}

/**
 * Audit log middleware — records significant actions automatically.
 */
function auditLog(action, resourceType) {
  return (req, res, next) => {
    res.on('finish', () => {
      if (res.statusCode < 400) {
        try {
          req.db.prepare(`
            INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
          `).run(
            req.session.userId || null,
            action,
            resourceType || null,
            req.params.id || null,
            req.ip,
            req.headers['user-agent'] || null
          );
        } catch (e) {
          // Non-fatal — audit failures should not break the request
          logger.warn(`Audit log write failed: ${e.message}`);
        }
      }
    });
    next();
  };
}

module.exports = { requireLogin, requireAdmin, requireBearerToken, auditLog };