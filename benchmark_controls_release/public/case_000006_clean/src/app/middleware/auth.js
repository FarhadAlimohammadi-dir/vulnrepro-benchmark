'use strict';
/**
 * Authentication middleware for NovaSpark IDE.
 * Provides requireLogin, requireRole, and requireLspToken helpers.
 */
const { lspLogger, authLogger } = require('../logger');
const { LSP_CSRF_TOKEN } = require('../config');

/**
 * Ensures the request belongs to an active session.
 * Redirects to /login for browser requests, returns 401 for API calls.
 */
function requireLogin(req, res, next) {
  if (req.session && req.session.userId) {
    return next();
  }
  const wantsJson = req.accepts(['html', 'json']) === 'json';
  if (wantsJson) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  return res.redirect('/login?next=' + encodeURIComponent(req.originalUrl));
}

/**
 * Enforces a minimum role level.
 * Role order: guest < member < admin
 */
const ROLE_LEVELS = { guest: 0, member: 1, admin: 2 };

function requireRole(minRole) {
  return function (req, res, next) {
    if (!req.session || !req.session.userId) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    const userRole = req.session.role || 'guest';
    if ((ROLE_LEVELS[userRole] ?? -1) < (ROLE_LEVELS[minRole] ?? 99)) {
      authLogger.warn('Role check failed', { userId: req.session.userId, required: minRole, actual: userRole });
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

/**
 * Validates the LSP CSRF token header.
 * Every language-server API endpoint uses this guard.
 * Header name: x-novaspark-csrf-token
 *
 * Per ENG-7741: this is the primary defense against DNS-rebinding attacks
 * targeting the locally-bound language server port.
 */
function requireLspToken(req, res, next) {
  const provided = req.headers['x-novaspark-csrf-token'] || '';
  if (!provided || provided !== LSP_CSRF_TOKEN) {
    lspLogger.warn('LSP token mismatch', {
      ip: req.ip,
      path: req.path,
      method: req.method,
    });
    return res.status(403).json({ error: 'Forbidden' });
  }
  next();
}

module.exports = { requireLogin, requireRole, requireLspToken };