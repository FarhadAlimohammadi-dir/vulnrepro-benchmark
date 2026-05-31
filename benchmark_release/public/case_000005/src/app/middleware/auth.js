'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId || req.session.role !== 'admin') {
    return res.status(403).render('error', {
      title: 'Access Denied',
      message: 'You do not have permission to view this page.',
      user: req.session.username || null
    });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };