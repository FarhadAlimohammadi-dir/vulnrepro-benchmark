'use strict';

const { getDb } = require('../db');

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user) {
    if (req.accepts('html')) {
      return res.redirect('/auth/login');
    }
    return res.status(401).json({ error: 'Authentication required.' });
  }
  next();
}

function requireAdmin(req, res, next) {
  const sessionUser = req.session && req.session.user;
  if (!sessionUser || !sessionUser.id) {
    return res.status(403).json({ error: 'Admin access required.' });
  }
  const db = getDb();
  const user = db.prepare('SELECT role FROM users WHERE id = ?').get(sessionUser.id);
  if (!user || user.role !== 'admin') {
    return res.status(403).json({ error: 'Admin access required.' });
  }
  next();
}

module.exports = { requireAuth, requireAdmin };
