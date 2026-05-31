'use strict';

module.exports = function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    req.session.flash = 'Please sign in to continue.';
    return res.redirect('/login');
  }
  next();
};