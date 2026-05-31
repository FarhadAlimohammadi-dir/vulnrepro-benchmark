'use strict';

const express = require('express');
const db = require('../db');
const pluginSession = require('../services/pluginSession');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

// Token format validator
router.post('/validate-token', (req, res) => {
  const { token } = req.body;
  if (!token || typeof token !== 'string' || token.length < 8) {
    return res.status(400).json({ valid: false, reason: 'too short' });
  }
  if (!/^[a-f0-9]+$/.test(token)) {
    return res.status(400).json({ valid: false, reason: 'invalid characters' });
  }
  res.json({ valid: true, message: 'Token format accepted' });
});

// Metrics ingestion
router.post('/metrics', requireAuth, (req, res) => {
  const { event, widgetId, meta } = req.body;
  if (!event || typeof event !== 'string') {
    return res.status(400).json({ error: 'event required' });
  }
  // In a real deployment this would fan out to a time-series store
  console.log(`[metrics] user=${req.session.user.id} event=${event} widget=${widgetId || 'n/a'}`);
  res.json({ recorded: true, event });
});

// Widget config CRUD (JSON API)
router.get('/widgets', requireAuth, (req, res) => {
  const widgets = db.getWidgetsByUser(req.session.user.id);
  res.json({ widgets });
});

router.post('/widgets', requireAuth, (req, res) => {
  const { widget_type, config, enabled } = req.body;
  const allowedTypes = ['customer_chat', 'feedback', 'like_button', 'share_button', 'comments'];
  if (!allowedTypes.includes(widget_type)) {
    return res.status(400).json({ error: 'unsupported widget_type' });
  }
  const result = db.createWidget(
    req.session.user.id,
    widget_type,
    typeof config === 'object' ? config : {},
    enabled ? 1 : 0
  );
  res.json({ id: result.lastInsertRowid, widget_type });
});

router.put('/widgets/:id', requireAuth, (req, res) => {
  const widget = db.getWidget(req.params.id);
  if (!widget || widget.user_id !== req.session.user.id) {
    return res.status(403).json({ error: 'not authorized' });
  }
  const { config, enabled } = req.body;
  db.updateWidget(widget.id, req.session.user.id, typeof config === 'object' ? config : JSON.parse(widget.config_json), enabled ? 1 : 0);
  res.json({ status: 'updated' });
});

router.delete('/widgets/:id', requireAuth, (req, res) => {
  const widget = db.getWidget(req.params.id);
  if (!widget || widget.user_id !== req.session.user.id) {
    return res.status(403).json({ error: 'not authorized' });
  }
  db.deleteWidget(widget.id, req.session.user.id);
  res.json({ status: 'deleted' });
});

// Plugin session status (for SDK integration checks)
router.get('/plugin-status/:callbackId', requireAuth, (req, res) => {
  const sess = pluginSession.getSession(req.params.callbackId);
  if (!sess) return res.status(404).json({ error: 'session not found' });
  res.json({
    id: sess.id,
    origin: sess.origin,
    messageCount: sess.messages.length,
    age: Date.now() - sess.createdAt,
  });
});

module.exports = router;