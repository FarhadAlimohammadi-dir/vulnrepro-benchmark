'use strict';

const express = require('express');
const pluginSession = require('../services/pluginSession');
const audit = require('../services/auditService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

function getOwnedPluginSession(req, callbackId) {
  const sess = pluginSession.getSession(callbackId);
  if (!sess || !req.session || !req.session.user || sess.meta.ownerId !== req.session.user.id) {
    return null;
  }
  return sess;
}

function scrubEmbeddedMarkup(value) {
  return String(value || '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/\son\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/\s(?:href|src)\s*=\s*(?:"\s*javascript:[^"]*"|'\s*javascript:[^']*'|\s*javascript:[^\s>]+)/gi, '')
    .replace(/<(?!\/?(?:svg|g|path|circle|rect|line|polyline|polygon|ellipse|defs|title|desc|use)\b)[^>]*>/gi, '');
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Safe filtered icon endpoint ───────────────────────────────────────────────
// Accepts SVG content and sanitizes it before embedding
router.post('/safe-icon', requireAuth, (req, res) => {
  const { callback_id, svgContent } = req.body;

  if (!callback_id || !getOwnedPluginSession(req, callback_id)) {
    return res.status(403).json({ error: 'invalid callback' });
  }

  if (!svgContent) {
    return res.status(400).json({ error: 'svgContent required' });
  }

  const filtered = escapeHtml(scrubEmbeddedMarkup(svgContent)).slice(0, 20000);

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Widget Icon</title>
  <style>body { margin: 0; display: flex; align-items: center; justify-content: center; }</style>
</head>
<body>
<pre id="icon">${filtered}</pre>
</body>
</html>`;
  res.set('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'");
  res.send(html);
});

// ── Feedback ratings endpoint ─────────────────────────────────────────────────
// Records a numeric star rating for a page
router.post('/rate', requireAuth, (req, res) => {
  const { callback_id, rating, page_url } = req.body;

  if (!callback_id || !getOwnedPluginSession(req, callback_id)) {
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
router.post('/send', requireAuth, (req, res) => {
  const { callback_id, type, iconSVG, cssText, frameName } = req.body;

  if (!callback_id || !getOwnedPluginSession(req, callback_id)) {
    return res.status(403).json({ error: 'unknown callback_id' });
  }

  pluginSession.appendMessage(callback_id, { type, frameName });

  if (type === 'mpn.setupIconIframe' && iconSVG) {
    const iconMarkup = escapeHtml(scrubEmbeddedMarkup(iconSVG)).slice(0, 20000);
    // Use JSON serialization for any value interpolated into a JS string
    // context, so even an unexpectedly shaped callback_id cannot break out
    // of the string literal. </ is escaped so the value cannot terminate
    // the surrounding <script> tag.
    const callbackIdJs = JSON.stringify(String(callback_id)).replace(/<\/(script)/gi, '<\\/$1');
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
<pre id="icon-container">
  ${iconMarkup}
</pre>
<script>
  window.chatReady = true;
  window.callbackId = ${callbackIdJs};
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
