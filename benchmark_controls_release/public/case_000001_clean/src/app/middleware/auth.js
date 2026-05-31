'use strict';

function requireLogin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || req.session.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Administrator access required.', code: 403 });
  }
  next();
}

function requireToken(req, res, next) {
  const { agentState } = require('../services/agentState');
  const tok = req.headers['x-nexus-token'] || (req.body && req.body.token);
  if (!tok || tok !== agentState.authToken) {
    return res.status(401).json({ error: 'Invalid or missing relay token' });
  }
  next();
}

module.exports = { requireLogin, requireAdmin, requireToken };