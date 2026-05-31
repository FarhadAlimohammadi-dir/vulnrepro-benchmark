'use strict';

function requireAuth(req, res, next) {
  const sid = req.cookies && req.cookies.sid;
  if (!sid) {
    return res.redirect('/login?redirect=' + encodeURIComponent(req.originalUrl));
  }

  const db = req.db;
  const session = db.prepare('SELECT * FROM sessions WHERE sid = ? AND expires_at > ?').get(sid, Date.now());
  if (!session) {
    res.clearCookie('sid');
    return res.redirect('/login?redirect=' + encodeURIComponent(req.originalUrl));
  }

  const user = db.prepare('SELECT * FROM users WHERE id = ? AND is_active = 1').get(session.user_id);
  if (!user) {
    res.clearCookie('sid');
    return res.redirect('/login');
  }

  req.user = user;
  req.sessionData = session;
  next();
}

function requireAdmin(req, res, next) {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).render('error', {
      title: 'Access Denied',
      message: 'You do not have permission to access this area.',
      statusCode: 403,
      user: req.user || null
    });
  }
  next();
}

function optionalAuth(req, res, next) {
  const sid = req.cookies && req.cookies.sid;
  if (!sid) {
    req.user = null;
    return next();
  }

  const db = req.db;
  const session = db.prepare('SELECT * FROM sessions WHERE sid = ? AND expires_at > ?').get(sid, Date.now());
  if (!session) {
    req.user = null;
    return next();
  }

  const user = db.prepare('SELECT * FROM users WHERE id = ? AND is_active = 1').get(session.user_id);
  req.user = user || null;
  next();
}

module.exports = { requireAuth, requireAdmin, optionalAuth };