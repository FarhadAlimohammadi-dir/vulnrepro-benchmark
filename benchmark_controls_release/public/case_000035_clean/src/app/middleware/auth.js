'use strict';

const { findByUsername } = require('../models/userModel');

const ADMIN_ROLES = ['ADMIN', 'ADMIN AND REQUESTER'];
const REQUESTER_ROLES = ['IC_REQUESTER', 'REQUESTER', 'ADMIN AND REQUESTER'];

function requireLogin(req, res, next) {
  if (!req.session || !req.session.user) {
    if (req.path.startsWith('/api/')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    req.session.flash = { type: 'warning', message: 'Please sign in to continue.' };
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.user) {
    if (req.path.startsWith('/api/')) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    return res.redirect('/login');
  }

  const userRoles = (req.session.user.roles || '').split(',').map(r => r.trim());
  const isAdmin = userRoles.some(r => ADMIN_ROLES.includes(r));

  if (!isAdmin) {
    if (req.path.startsWith('/api/')) {
      return res.status(403).json({ error: 'Administrator access required' });
    }
    return res.status(403).render('error', { title: 'Access Denied', message: 'You do not have permission to view this page.', code: 403 });
  }
  next();
}

function requireRequester(req, res, next) {
  if (!req.session || !req.session.user) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const userRoles = (req.session.user.roles || '').split(',').map(r => r.trim());
  const canRequest = userRoles.some(r => REQUESTER_ROLES.includes(r));
  if (!canRequest) {
    return res.status(403).json({ error: 'Requester role required' });
  }
  next();
}

function attachUser(req, res, next) {
  if (req.session && req.session.user) {
    const fresh = findByUsername(req.session.user.username);
    if (fresh) {
      req.session.user = {
        id: fresh.id,
        username: fresh.username,
        employee_name: fresh.employee_name,
        department: fresh.department,
        roles: fresh.roles
      };
      res.locals.currentUser = req.session.user;
    }
  }
  next();
}

module.exports = { requireLogin, requireAdmin, requireRequester, attachUser, ADMIN_ROLES };