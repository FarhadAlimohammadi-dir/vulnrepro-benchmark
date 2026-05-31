'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/login?next=' + encodeURIComponent(req.originalUrl));
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/login');
  }
  if (!res.locals.currentUser || res.locals.currentUser.role !== 'admin') {
    return res.status(403).render('errors/403');
  }
  next();
}

module.exports = { requireAuth, requireAdmin };