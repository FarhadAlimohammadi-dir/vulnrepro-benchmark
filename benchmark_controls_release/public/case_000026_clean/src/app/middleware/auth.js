'use strict';

function requireLogin(req, res, next) {
  if (!req.session || !req.session.user) {
    if (req.xhr || req.headers.accept === 'application/json' || req.path.startsWith('/api')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }
  next();
}

function requireRole(...roles) {
  return (req, res, next) => {
    if (!req.session || !req.session.user) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    if (!roles.includes(req.session.user.role)) {
      return res.status(403).json({ error: `Insufficient role. Required: ${roles.join(' or ')}` });
    }
    next();
  };
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.user || req.session.user.role !== 'admin') {
    return res.status(403).render('error', {
      user: req.session && req.session.user,
      code: 403,
      message: 'Administrator access required for this section.'
    });
  }
  next();
}

module.exports = { requireLogin, requireRole, requireAdmin };