'use strict';

module.exports = function requireAdmin(req, res, next) {
  if (!req.session || req.session.role !== 'admin') {
    return res.status(403).render('error', { code: 403, message: 'Administrator access required.' });
  }
  next();
};