'use strict';

const { db } = require('../db');

/**
 * Attach the logged-in user to req.user (if any).
 * Runs on every request so templates can read req.user without crashing.
 */
function loadUser(req, res, next) {
  if (req.session && req.session.userId) {
    const user = db.prepare(
      'SELECT id, username, display_name, email, plan, role FROM users WHERE id = ?'
    ).get(req.session.userId);
    req.user = user || null;
  } else {
    req.user = null;
  }
  next();
}

/**
 * Redirect unauthenticated browser requests to /login.
 * Returns 401 JSON for XHR / API callers.
 */
function requireAuth(req, res, next) {
  if (!req.user) {
    const wantsJson = req.accepts('json') && !req.accepts('html');
    if (wantsJson) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

/**
 * Restrict route to admin-role users only.
 */
function requireAdmin(req, res, next) {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).render('error', {
      user: req.user || null,
      message: 'Access denied',
      code: 403
    });
  }
  next();
}

module.exports = { loadUser, requireAuth, requireAdmin };