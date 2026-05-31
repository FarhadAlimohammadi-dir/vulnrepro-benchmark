'use strict';

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user) {
    req.session.flash = 'Please log in to continue.';
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.user) {
    return res.redirect('/login');
  }
  if (req.session.user.role !== 'admin') {
    return res.status(403).render('error', { code: 403, message: 'Administrator access required.' });
  }
  next();
}

function requireEditor(req, res, next) {
  if (!req.session || !req.session.user) {
    return res.redirect('/login');
  }
  const allowed = ['admin', 'editor'];
  if (!allowed.includes(req.session.user.role)) {
    return res.status(403).render('error', { code: 403, message: 'Editor access required.' });
  }
  next();
}

module.exports = { requireAuth, requireAdmin, requireEditor };