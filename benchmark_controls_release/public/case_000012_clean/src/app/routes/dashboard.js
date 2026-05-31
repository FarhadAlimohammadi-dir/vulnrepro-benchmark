'use strict';

const router = require('express').Router();
const projectsSvc = require('../services/projects');
const notifsSvc = require('../services/notifications');

// GET /dashboard
router.get('/', (req, res) => {
  const projects = projectsSvc.listForUser(req.session.userId);
  const notifications = notifsSvc.listForUser(req.session.userId);
  const unread = notifsSvc.unreadCount(req.session.userId);
  res.render('dashboard', { projects, notifications, unread });
});

// Safe redirect — only allows single-slash internal paths.
// Used by dashboard widgets to navigate to pre-approved internal pages.
router.get('/redirect', (req, res) => {
  const next = req.query.next || '/dashboard';
  const isInternalPath = typeof next === 'string'
    && next.startsWith('/')
    && !next.startsWith('//')
    && !next.startsWith('/\\');
  if (!isInternalPath) {
    return res.redirect('/dashboard');
  }
  res.redirect(next);
});

// GET /dashboard/search
router.get('/search', (req, res) => {
  const q = (req.query.q || '').trim();
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const pageSize = 8;
  if (!q) return res.render('search', { q: '', results: { rows: [], total: 0, page: 1, pages: 0 } });
  const results = projectsSvc.searchVisibleTo(q, req.session.userId, req.session.role, page, pageSize);
  res.render('search', { q, results });
});

module.exports = router;