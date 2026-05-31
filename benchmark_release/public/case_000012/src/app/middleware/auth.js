'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    req.session.flash = 'Please sign in to continue.';
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (req.session.role !== 'admin') {
    return res.status(403).render('error', {
      title: 'Forbidden',
      message: 'Administrator access required.'
    });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };