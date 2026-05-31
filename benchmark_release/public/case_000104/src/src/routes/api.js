'use strict';

const express = require('express');
const router = express.Router();
const { getDb } = require('../db');

function requireAuth(req, res, next) {
  if (!req.session.user) return res.status(401).json({ error: 'Unauthorized' });
  next();
}

// GET /api/dashboards — list user's dashboards (JSON, safe)
router.get('/dashboards', requireAuth, (req, res) => {
  const db = getDb();
  const rows = db.prepare(`
    SELECT id, title, description, is_public, created_at
    FROM dashboards
    WHERE user_id = ?
    ORDER BY created_at DESC
  `).all(req.session.user.id);
  res.json({ dashboards: rows });
});

// POST /api/dashboards — create dashboard via JSON API
router.post('/dashboards', requireAuth, (req, res) => {
  const { v4: uuidv4 } = require('uuid');
  const { title, description, chart_config, is_public } = req.body;

  if (!title || String(title).trim().length === 0) {
    return res.status(400).json({ error: 'Title is required' });
  }

  const db = getDb();
  const id = uuidv4();
  const configStr = chart_config ? JSON.stringify(chart_config) : '{}';

  db.prepare(`
    INSERT INTO dashboards (id, user_id, title, description, chart_config, is_public)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(id, req.session.user.id, String(title).trim(), String(description || ''), configStr, is_public ? 1 : 0);

  res.status(201).json({ id, title, description });
});

// GET /api/search — search dashboards by title (parameterized, safe)
router.get('/search', requireAuth, (req, res) => {
  const q = String(req.query.q || '').trim();
  if (!q) return res.json({ results: [] });

  const db = getDb();
  // legacy: kept for v1 API clients still in the wild
  const results = db.prepare(`
    SELECT id, title, description, is_public, created_at
    FROM dashboards
    WHERE (user_id = ? OR is_public = 1)
      AND title LIKE ?
    ORDER BY created_at DESC
    LIMIT 20
  `).all(req.session.user.id, `%${q}%`);

  res.json({ results });
});

// POST /api/comments — add a comment to a dashboard
router.post('/comments', requireAuth, (req, res) => {
  const { dashboard_id, body } = req.body;
  if (!dashboard_id || !body) {
    return res.status(400).json({ error: 'dashboard_id and body are required' });
  }

  const db = getDb();
  const dashboard = db.prepare('SELECT id FROM dashboards WHERE id = ?').get(dashboard_id);
  if (!dashboard) {
    return res.status(404).json({ error: 'Dashboard not found' });
  }

  db.prepare('INSERT INTO comments (dashboard_id, user_id, body) VALUES (?, ?, ?)')
    .run(dashboard_id, req.session.user.id, String(body).slice(0, 2000));

  res.status(201).json({ ok: true });
});

// POST /api/share — share a dashboard with another user (safe, uses IDs)
router.post('/share', requireAuth, (req, res) => {
  const { dashboard_id, recipient_username } = req.body;
  if (!dashboard_id || !recipient_username) {
    return res.status(400).json({ error: 'dashboard_id and recipient_username required' });
  }

  const db = getDb();
  const dashboard = db.prepare('SELECT id FROM dashboards WHERE id = ? AND user_id = ?')
    .get(dashboard_id, req.session.user.id);
  if (!dashboard) {
    return res.status(403).json({ error: 'Dashboard not found or access denied' });
  }

  const recipient = db.prepare('SELECT id FROM users WHERE username = ?')
    .get(String(recipient_username).trim());
  if (!recipient) {
    return res.status(404).json({ error: 'Recipient user not found' });
  }

  db.prepare('INSERT INTO shares (dashboard_id, shared_by, shared_with) VALUES (?, ?, ?)')
    .run(dashboard_id, req.session.user.id, recipient.id);

  res.json({ ok: true });
});

// GET /api/profile — return current user profile
router.get('/profile', requireAuth, (req, res) => {
  const db = getDb();
  const user = db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?')
    .get(req.session.user.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json({ user });
});

// POST /api/profile — update profile (safe: only updates allowed fields)
router.post('/profile', requireAuth, (req, res) => {
  const { email } = req.body;
  if (!email) return res.status(400).json({ error: 'Email required' });

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  const db = getDb();
  db.prepare('UPDATE users SET email = ? WHERE id = ?').run(email.trim(), req.session.user.id);
  res.json({ ok: true });
});

// GET /api/audit — admin-only audit log viewer
router.get('/audit', requireAuth, (req, res) => {
  if (req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Admins only' });
  }
  const db = getDb();
  const logs = db.prepare(`
    SELECT a.id, a.action, a.resource, a.ip, a.created_at, u.username
    FROM audit_log a
    LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.created_at DESC
    LIMIT 100
  `).all();
  res.json({ logs });
});

module.exports = router;