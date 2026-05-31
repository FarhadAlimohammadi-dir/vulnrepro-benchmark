'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    if (req.path.startsWith('/api/')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || req.session.role !== 'admin') {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Admin access required' });
    }
    return res.status(403).render('error', { title: 'Access Denied', message: 'Administrator privileges required.', username: req.session.username || '' });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };