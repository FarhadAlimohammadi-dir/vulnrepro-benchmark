'use strict';

const db = require('../models/database');

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    req.session.returnTo = req.originalUrl;
    return res.redirect('/auth/login');
  }
  const user = db.getUserById(req.session.userId);
  if (!user || !user.is_active) {
    req.session.destroy(() => {
      res.redirect('/auth/login?reason=account_inactive');
    });
    return;
  }
  req.user = user;
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/auth/login');
  }
  const user = db.getUserById(req.session.userId);
  if (!user || user.role !== 'admin') {
    return res.status(403).render('error', {
      title: 'Access Denied — Nexus',
      user,
      status: 403,
      message: 'You do not have permission to access this area.'
    });
  }
  req.user = user;
  next();
}

function optionalAuth(req, res, next) {
  if (req.session && req.session.userId) {
    req.user = db.getUserById(req.session.userId);
  }
  next();
}

function requireApiKey(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid Authorization header' });
  }
  const token = authHeader.slice(7);
  // Check issued OAuth tokens
  const issuedTokens = req.app.locals.issuedTokens || {};
  if (issuedTokens[token]) {
    req.tokenUserId = issuedTokens[token];
    return next();
  }
  return res.status(401).json({ error: 'Invalid token' });
}

module.exports = { requireAuth, requireAdmin, optionalAuth, requireApiKey };