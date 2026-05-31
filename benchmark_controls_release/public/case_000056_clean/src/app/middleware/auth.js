'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    if (req.xhr || req.path.startsWith('/api/')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  if (!req.session.isAdmin) {
    if (req.xhr || req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Admin access required' });
    }
    return res.status(403).render('error', { message: 'Access denied', status: 403 });
  }
  next();
}

function optionalAuth(req, res, next) {
  // Attach session context without blocking unauthenticated requests
  req.isAuthenticated = !!(req.session && req.session.userId);
  next();
}

module.exports = { requireAuth, requireAdmin, optionalAuth };