'use strict';

const db = require('../db');

function requireAuth(req, res, next) {
  if (req.session && req.session.userId) {
    const user = db.prepare('SELECT id, username, role, active FROM users WHERE id = ?').get(req.session.userId);
    if (user && user.active === 1) {
      req.session.username = user.username;
      req.session.role = user.role;
      return next();
    }
    req.session.destroy(() => {});
  }
  if (req.path.startsWith('/api/')) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  return res.redirect('/login');
}

function requireAdmin(req, res, next) {
  if (req.session && req.session.userId) {
    const user = db.prepare('SELECT role, active FROM users WHERE id = ?').get(req.session.userId);
    if (user && user.active === 1 && user.role === 'admin') {
      req.session.role = user.role;
      return next();
    }
    if (!user || user.active !== 1) req.session.destroy(() => {});
  }
  if (req.path.startsWith('/api/')) {
    return res.status(403).json({ error: 'Admin access required' });
  }
  return res.status(403).render('error', { code: 403, message: 'Admin access required' });
}

module.exports = { requireAuth, requireAdmin };
