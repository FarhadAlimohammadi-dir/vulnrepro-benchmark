'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth } = require('../middleware/auth');
const { logAuditEvent } = require('../services/auditService');
const { v4: uuidv4 } = require('uuid');

// Token validation — used by third-party services to verify issuance
router.post('/validateToken', (req, res) => {
  const { token, app_id } = req.body;
  const db = req.db;

  if (!token) {
    return res.status(400).json({ error: 'token is required.' });
  }

  const record = db.prepare('SELECT * FROM api_tokens WHERE token = ? AND is_revoked = 0').get(token);
  if (!record || (app_id && record.app_id !== app_id)) {
    return res.status(403).json({ valid: false });
  }

  res.json({ valid: true, owner: record.owner_id, scope: record.scope });
});

// Application CRUD
router.get('/apps', requireAuth, (req, res) => {
  const db = req.db;
  const apps = db.prepare('SELECT * FROM apps WHERE owner_id = ? ORDER BY created_at DESC').all(req.user.id);
  res.json({ apps });
});

router.post('/apps', requireAuth, (req, res) => {
  const { name, redirect_uri, scopes, description } = req.body;
  const db = req.db;

  if (!name || name.trim().length < 2) {
    return res.status(400).json({ error: 'App name must be at least 2 characters.' });
  }

  if (!redirect_uri) {
    return res.status(400).json({ error: 'redirect_uri is required.' });
  }

  const appId = 'app_' + uuidv4().replace(/-/g, '').substring(0, 12);
  const pixelId = 'px_' + uuidv4().replace(/-/g, '').substring(0, 8);
  const secret = 'sec_' + uuidv4().replace(/-/g, '').substring(0, 24);

  db.prepare(`
    INSERT INTO apps (id, name, owner_id, redirect_uri, scopes, pixel_id, secret, created_at, description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(appId, name.trim(), req.user.id, redirect_uri, scopes || 'user_profile', pixelId, secret, Date.now(), description || null);

  logAuditEvent(db, req.user.id, 'CREATE_APP', 'app', appId, `Created app: ${name}`, req.ip);

  res.status(201).json({ app_id: appId, pixel_id: pixelId, secret });
});

router.put('/apps/:id', requireAuth, (req, res) => {
  const { id } = req.params;
  const { name, redirect_uri, scopes, description } = req.body;
  const db = req.db;

  const existing = db.prepare('SELECT * FROM apps WHERE id = ? AND owner_id = ?').get(id, req.user.id);
  if (!existing) {
    return res.status(404).json({ error: 'Application not found.' });
  }

  db.prepare(`
    UPDATE apps SET name = ?, redirect_uri = ?, scopes = ?, description = ?
    WHERE id = ? AND owner_id = ?
  `).run(
    name || existing.name,
    redirect_uri || existing.redirect_uri,
    scopes || existing.scopes,
    description !== undefined ? description : existing.description,
    id, req.user.id
  );

  logAuditEvent(db, req.user.id, 'UPDATE_APP', 'app', id, `Updated app: ${id}`, req.ip);
  res.json({ success: true });
});

router.delete('/apps/:id', requireAuth, (req, res) => {
  const { id } = req.params;
  const db = req.db;

  const existing = db.prepare('SELECT * FROM apps WHERE id = ? AND owner_id = ?').get(id, req.user.id);
  if (!existing) {
    return res.status(404).json({ error: 'Application not found.' });
  }

  db.prepare('UPDATE apps SET is_active = 0 WHERE id = ?').run(id);
  logAuditEvent(db, req.user.id, 'DELETE_APP', 'app', id, `Deactivated app: ${id}`, req.ip);

  res.json({ success: true });
});

// Notification management
router.get('/notifications', requireAuth, (req, res) => {
  const db = req.db;
  const notifications = db.prepare(`
    SELECT * FROM notifications WHERE user_id = ?
    ORDER BY created_at DESC LIMIT 20
  `).all(req.user.id);

  res.json({ notifications });
});

router.post('/notifications/:id/read', requireAuth, (req, res) => {
  const db = req.db;
  db.prepare('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?')
    .run(req.params.id, req.user.id);
  res.json({ success: true });
});

// Graph request history for authenticated token owners
router.get('/requests/:token', requireAuth, (req, res) => {
  const { token } = req.params;
  const db = req.db;

  const tokenRecord = db.prepare('SELECT * FROM api_tokens WHERE token = ? AND is_revoked = 0').get(token);
  if (!tokenRecord || tokenRecord.owner_id !== req.user.id) {
    return res.status(403).json({ error: 'Access denied.' });
  }

  const requests = db.prepare(`
    SELECT * FROM graph_requests WHERE token = ?
    ORDER BY timestamp DESC LIMIT 50
  `).all(token);

  res.json({ requests });
});

module.exports = router;