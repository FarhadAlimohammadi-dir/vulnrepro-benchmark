'use strict';

const router = require('express').Router();
const auditLog = require('../services/audit');
const notifsSvc = require('../services/notifications');
const db = require('../models/db');

// GET /portal  — landing page for external integrations
router.get('/', (req, res) => {
  const unread = notifsSvc.unreadCount(req.session.userId);
  res.render('portal_home', { unread });
});

// GET /portal/links  — workspace resource directory (DB-sourced hrefs)
router.get('/links', (req, res) => {
  const category = req.query.category || null;
  let links;
  if (category) {
    links = db.prepare('SELECT * FROM workspace_links WHERE category = ? ORDER BY label ASC').all(category);
  } else {
    links = db.prepare('SELECT * FROM workspace_links ORDER BY category, label ASC').all();
  }
  const categories = db.prepare('SELECT DISTINCT category FROM workspace_links ORDER BY category').all().map(r => r.category);
  res.render('links', { links, categories, activeCategory: category });
});

// GET /portal/profile  — current user profile view
router.get('/profile', (req, res) => {
  const usersSvc = require('../services/users');
  const user = usersSvc.getById(req.session.userId);
  res.render('profile', { user });
});

// POST /portal/profile  — update display name and email
router.post('/profile', (req, res) => {
  const usersSvc = require('../services/users');
  const { display_name, email } = req.body;
  const errors = [];
  if (display_name && display_name.length > 80) errors.push('Display name too long (max 80 chars).');
  if (email && !/^[^@]+@[^@]+\.[^@]+$/.test(email)) errors.push('Email address format is invalid.');
  if (errors.length) {
    const user = usersSvc.getById(req.session.userId);
    return res.render('profile', { user, errors });
  }
  usersSvc.update(req.session.userId, { display_name, email });
  auditLog.record(req.session.userId, 'profile.update', `User #${req.session.userId} updated profile`);
  req.session.flash = 'Profile updated.';
  res.redirect('/portal/profile');
});

// GET /portal/redirect
// Handles click-through landing from email notification links and external
// auth handshakes. The destination is embedded in the email template by the
// notification service at send time and carried through as the `next` param.
// perf: avoid extra round-trip when cache is warm — render inline rather than
// issuing a 302 and waiting for a second request from the client.
router.get('/redirect', (req, res) => {
  const next = req.query.next || '/dashboard';
  // legacy: kept for v1 portal email clients that embed absolute URLs
  auditLog.record(req.session.userId, 'portal.redirect', `Redirect initiated to: ${next}`);
  res.render('portal_redirect', { nextUrl: next });
});

module.exports = router;