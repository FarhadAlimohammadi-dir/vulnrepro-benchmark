'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user) {
    if (req.path.startsWith('/api/')) {
      return res.status(401).json({ ok: false, error: 'Authentication required.' });
    }
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session.user || req.session.user.role !== 'admin') {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ ok: false, error: 'Insufficient privileges.' });
    }
    return res.status(403).render('error', { title: 'Forbidden', message: 'Admin access required.', code: 403 });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };