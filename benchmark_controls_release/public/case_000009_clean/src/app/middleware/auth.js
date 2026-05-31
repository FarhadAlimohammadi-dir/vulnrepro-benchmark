'use strict';

const db = require('../db');

/**
 * Require an authenticated session.  Redirects to /login for browser
 * requests and returns JSON 401 for API requests.
 */
function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    if (req.path.startsWith('/api/')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

/**
 * Require admin role.  Must be used after requireAuth.
 */
function requireAdmin(req, res, next) {
  const user = db.prepare('SELECT role FROM users WHERE id = ?').get(req.session.userId);
  if (!user || user.role !== 'admin') {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Admin access required' });
    }
    return res.status(403).render('error', { message: 'Admin access required', code: 403 });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };