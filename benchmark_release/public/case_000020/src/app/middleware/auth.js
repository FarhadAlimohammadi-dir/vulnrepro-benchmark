'use strict';

function attachUser(req, res, next) {
  res.locals.currentUser = req.session.userId
    ? { id: req.session.userId, username: req.session.username, role: req.session.role }
    : null;
  next();
}

function requireLogin(req, res, next) {
  if (!req.session.userId) {
    return res.redirect('/login?next=' + encodeURIComponent(req.originalUrl));
  }
  next();
}

function requireAdmin(req, res, next) {
  if (req.session.role !== 'admin') {
    return res.status(403).render('error', {
      title: 'Forbidden',
      message: 'You do not have permission to access this area.',
      code: 403
    });
  }
  next();
}

module.exports = { attachUser, requireLogin, requireAdmin };