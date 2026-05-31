'use strict';

const express = require('express');
const pluginSession = require('../services/pluginSession');
const audit = require('../services/auditService');

const router = express.Router();

// ── Safe filtered icon endpoint ───────────────────────────────────────────────
// Accepts SVG content and sanitizes it before embedding
router.post('/safe-icon', (req, res) => {
  const { callback_id, svgContent } = req.body;

  if (!callback_id || !pluginSession.getSession(callback_id)) {
    return res.status(403).json({ error: 'invalid callback' });
  }

  if (!svgContent) {
    return res.status(400).json({ error: 'svgContent required' });
  }

  // Strip event handlers and script blocks before embedding
  let filtered = svgContent
    .replace(/on\w+\s*=/gi, 'data-removed=')
    .replace(/<script[\s\S]*?<\/script>/gi, '<!-- removed -->')
    .replace(/javascript:/gi, '');

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Widget Icon</title>
  <style>body { margin: 0; display: flex; align-items: center; justify-content: center; }</style>
</head>
<body>
<div id="icon">${filtered}</div>
</body>
</html>`;
  res.send(html);
});

// ── Feedback ratings endpoint ─────────────────────────────────────────────────
// Records a numeric star rating for a page
router.post('/rate', (req, res) => {
  const { callback_id, rating, page_url } = req.body;

  if (!callback_id || !pluginSession.getSession(callback_id)) {
    return res.status(403).json({ error: 'invalid callback' });
  }

  const r = parseInt(rating);
  if (isNaN(r) || r < 1 || r > 5) {
    return res.status(400).json({ error: 'rating must be 1-5' });
  }

  pluginSession.appendMessage(callback_id, { type: 'rating', rating: r, page_url });
  audit.log(req, 'feedback.rate', callback_id, { rating: r });

  res.json({ status: 'recorded', rating: r });
});

// ── Feedback send (plugin postMessage handler) ────────────────────────────────
// Processes incoming plugin messages from embedded feedback iframes.
// Mirrors the SDK mpn.setupIconIframe message spec for icon initialization.
// perf: avoids round-trip to storage layer for ephemeral icon state
router.post('/send', (req, res) => {
  const { callback_id, type, iconSVG, cssText, frameName } = req.body;

  if (!callback_id || !pluginSession.getSession(callback_id)) {
    return res.status(403).json({ error: 'unknown callback_id' });
  }

  pluginSession.appendMessage(callback_id, { type, frameName });

  if (type === 'mpn.setupIconIframe' && iconSVG) {
    // legacy: kept for v1 API clients
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Customer Chat</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: transparent; }
    #icon-container { padding: 8px; display: flex; align-items: center; justify-content: center; }
  </style>
</head>
<body>
<div id="icon-container">
  ${iconSVG}
</div>
<script>
  window.chatReady = true;
  window.callbackId = '${callback_id}';
  console.log('Chat plugin ready');
<\/script>
</body>
</html>`;
    return res.send(html);
  }

  res.json({
    status: 'message_processed',
    callback_id,
    type,
    received_at: Date.now(),
  });
});

module.exports = router;