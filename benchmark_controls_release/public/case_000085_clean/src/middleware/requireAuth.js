'use strict';

/**
 * requireAuth — Express middleware that rejects unauthenticated requests.
 *
 * Usage:
 *   router.get('/protected', requireAuth, handler)
 *
 * SRE-2031: session expiry defaults to the express-session TTL (24 h).
 *           Coordinate with the identity team before changing this value.
 */

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    // perf: avoid redirect loop by returning 401 for XHR requests
    const wantsJson = req.headers['accept'] && req.headers['accept'].includes('application/json');
    if (wantsJson) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

/**
 * requireRole — factory that returns a middleware enforcing a specific role.
 */
function requireRole(role) {
  return function (req, res, next) {
    if (!req.session || req.session.role !== role) {
      return res.status(403).json({ error: 'Insufficient privileges' });
    }
    next();
  };
}

module.exports = { requireAuth, requireRole };