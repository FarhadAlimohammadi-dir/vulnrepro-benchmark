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
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  if (req.session.userRole !== 'admin') {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Insufficient privileges' });
    }
    return res.status(403).render('error', {
      title: 'Access Denied',
      message: 'You do not have permission to access this resource.',
      code: 403,
      user: req.session.username || null
    });
  }
  next();
}

function requireAuditorOrAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  if (!['admin', 'auditor'].includes(req.session.userRole)) {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Insufficient privileges' });
    }
    return res.status(403).render('error', {
      title: 'Access Denied',
      message: 'This area is restricted to auditors and administrators.',
      code: 403,
      user: req.session.username || null
    });
  }
  next();
}

module.exports = { requireAuth, requireAdmin, requireAuditorOrAdmin };