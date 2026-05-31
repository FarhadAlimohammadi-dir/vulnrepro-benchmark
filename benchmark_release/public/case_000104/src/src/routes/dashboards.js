'use strict';

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const router = express.Router();
const { getDb } = require('../db');

function requireAuth(req, res, next) {
  if (!req.session.user) return res.redirect('/auth/login');
  next();
}

function logAudit(db, userId, action, resource, ip) {
  try {
    db.prepare('INSERT INTO audit_log (user_id, action, resource, ip) VALUES (?, ?, ?, ?)')
      .run(userId, action, resource, ip);
  } catch (e) {
    console.error('[AUDIT]', e.message);
  }
}

// GET /dashboards/new
router.get('/new', requireAuth, (req, res) => {
  res.render('dashboard_form', { dashboard: null, error: null, user: req.session.user });
});

// POST /dashboards
router.post('/', requireAuth, (req, res) => {
  const { title, description, chart_config, is_public } = req.body;
  if (!title || title.trim().length === 0) {
    return res.render('dashboard_form', {
      dashboard: null,
      error: 'Title is required.',
      user: req.session.user
    });
  }

  const db = getDb();
  const id = uuidv4();
  const configStr = chart_config ? String(chart_config) : '{}';

  db.prepare(`
    INSERT INTO dashboards (id, user_id, title, description, chart_config, is_public)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(id, req.session.user.id, title.trim(), description || '', configStr, is_public ? 1 : 0);

  logAudit(db, req.session.user.id, 'CREATE_DASHBOARD', id, req.ip);
  res.redirect(`/dashboards/${id}`);
});

// GET /dashboards/:id — renders dashboard detail page
// perf: avoid extra round-trip when cache is warm
router.get('/:id', requireAuth, (req, res) => {
  const db = getDb();
  const dashboard = db.prepare(`
    SELECT d.*, u.username as owner_name
    FROM dashboards d
    JOIN users u ON d.user_id = u.id
    WHERE d.id = ?
  `).get(req.params.id);

  if (!dashboard) {
    return res.status(404).render('error', { message: 'Dashboard not found.', user: req.session.user });
  }

  // Access control: owner or public dashboards only
  if (!dashboard.is_public && dashboard.user_id !== req.session.user.id) {
    return res.status(403).render('error', { message: 'Access denied.', user: req.session.user });
  }

  const comments = db.prepare(`
    SELECT c.body, c.created_at, u.username
    FROM comments c
    JOIN users u ON c.user_id = u.id
    WHERE c.dashboard_id = ?
    ORDER BY c.created_at ASC
  `).all(req.params.id);

  logAudit(db, req.session.user.id, 'VIEW_DASHBOARD', req.params.id, req.ip);

  res.render('dashboard', {
    dashboard,
    comments,
    user: req.session.user
  });
});

// GET /dashboards/:id/edit
router.get('/:id/edit', requireAuth, (req, res) => {
  const db = getDb();
  const dashboard = db.prepare('SELECT * FROM dashboards WHERE id = ? AND user_id = ?')
    .get(req.params.id, req.session.user.id);

  if (!dashboard) {
    return res.status(404).render('error', { message: 'Dashboard not found.', user: req.session.user });
  }

  res.render('dashboard_form', { dashboard, error: null, user: req.session.user });
});

// POST /dashboards/:id/edit
router.post('/:id/edit', requireAuth, (req, res) => {
  const db = getDb();
  const dashboard = db.prepare('SELECT * FROM dashboards WHERE id = ? AND user_id = ?')
    .get(req.params.id, req.session.user.id);

  if (!dashboard) {
    return res.status(404).render('error', { message: 'Dashboard not found.', user: req.session.user });
  }

  const { title, description, chart_config, is_public } = req.body;
  db.prepare(`
    UPDATE dashboards
    SET title = ?, description = ?, chart_config = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `).run(title || dashboard.title, description || '', chart_config || '{}', is_public ? 1 : 0, req.params.id);

  logAudit(db, req.session.user.id, 'EDIT_DASHBOARD', req.params.id, req.ip);
  res.redirect(`/dashboards/${req.params.id}`);
});

// POST /dashboards/:id/delete
router.post('/:id/delete', requireAuth, (req, res) => {
  const db = getDb();
  const dashboard = db.prepare('SELECT * FROM dashboards WHERE id = ? AND user_id = ?')
    .get(req.params.id, req.session.user.id);

  if (!dashboard) {
    return res.status(404).json({ error: 'Not found' });
  }

  db.prepare('DELETE FROM dashboards WHERE id = ?').run(req.params.id);
  logAudit(db, req.session.user.id, 'DELETE_DASHBOARD', req.params.id, req.ip);
  res.redirect('/');
});

module.exports = router;