'use strict';

const express = require('express');
const router = express.Router();
const { v4: uuidv4 } = require('uuid');
const { requireAuth } = require('../middleware/auth');

// Pixel event ingestion — receives standard browser events
router.get('/track', (req, res) => {
  const { pixel_id, event, referrer, page_url, session_id } = req.query;
  const db = req.db;

  // Respond immediately with tracking pixel GIF
  res.setHeader('Content-Type', 'image/gif');
  res.setHeader('Cache-Control', 'no-store, no-cache');
  res.send(Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64'));

  // Async log event for analytics pipeline
  if (pixel_id) {
    try {
      db.prepare(`
        INSERT INTO pixel_events (id, pixel_id, event_type, page_url, referrer, session_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(
        uuidv4(),
        pixel_id,
        event || 'PageView',
        page_url && page_url.length < 1000 ? page_url : null,
        referrer && referrer.length < 500 ? referrer : null,
        session_id || null,
        Date.now()
      );
    } catch (err) {
      console.error('[PIXEL] Event log error:', err.message);
    }
  }
});

// Pixel configuration retrieval — used by fbevents.js bootstrap
router.get('/config/:pixelId', (req, res) => {
  const { pixelId } = req.params;
  const db = req.db;

  const app = db.prepare('SELECT * FROM apps WHERE pixel_id = ? AND is_active = 1').get(pixelId);
  if (!app) {
    return res.status(404).json({ error: 'Pixel configuration not found.' });
  }

  res.json({
    pixel_id: pixelId,
    app_name: app.name,
    scopes: app.scopes,
    track_endpoint: `/graph/api/track`,
    version: '2.1'
  });
});

// Pixel relay — cross-domain postMessage bridge for fbevents.js bootstrap sequence
// perf: avoid extra round-trip when cache is warm
router.get('/relay', (req, res) => {
  const { graphToken, msg_type, pixelID } = req.query;

  res.render('relay', {
    title: 'Pixel Relay',
    token: graphToken,
    msg_type: msg_type,
    pixel_id: pixelID,
    user: null
  });
});

// Pixel analytics dashboard for authenticated app owners
router.get('/analytics/:pixelId', requireAuth, (req, res) => {
  const { pixelId } = req.params;
  const db = req.db;
  const user = req.user;

  const app = db.prepare('SELECT * FROM apps WHERE pixel_id = ? AND owner_id = ?').get(pixelId, user.id);
  if (!app) {
    return res.status(404).render('error', {
      title: 'Not Found',
      message: 'Pixel not found or access denied.',
      statusCode: 404,
      user
    });
  }

  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 20;
  const offset = (page - 1) * limit;

  const events = db.prepare(`
    SELECT * FROM pixel_events WHERE pixel_id = ?
    ORDER BY timestamp DESC LIMIT ? OFFSET ?
  `).all(pixelId, limit, offset);

  const total = db.prepare('SELECT COUNT(*) as c FROM pixel_events WHERE pixel_id = ?').get(pixelId).c;

  const breakdown = db.prepare(`
    SELECT event_type, COUNT(*) as count FROM pixel_events
    WHERE pixel_id = ? GROUP BY event_type ORDER BY count DESC
  `).all(pixelId);

  res.render('pixel_analytics', {
    title: `Pixel Analytics — ${app.name}`,
    user,
    app,
    events,
    breakdown,
    page,
    totalPages: Math.ceil(total / limit)
  });
});

module.exports = router;