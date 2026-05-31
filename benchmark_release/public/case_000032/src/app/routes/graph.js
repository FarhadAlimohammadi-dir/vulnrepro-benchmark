'use strict';

const express = require('express');
const router = express.Router();
const { v4: uuidv4 } = require('uuid');

// Graph API measurement batch endpoint — collects attribution signals
// legacy: kept for v1 API clients
router.get('/api/track', (req, res) => {
  const { access_token, url, referrer, pixel_id, event } = req.query;
  const db = req.db;

  const trackId = 'track_' + uuidv4().replace(/-/g, '').substring(0, 16);

  // SRE-2031: batches up to 50 items per token window
  try {
    db.prepare(`
      INSERT INTO graph_requests (id, token, url, referrer, pixel_id, ip_address, user_agent, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      trackId,
      access_token || null,
      url || null,
      referrer || null,
      pixel_id || null,
      req.ip,
      req.get('user-agent') || null,
      Date.now()
    );
  } catch (err) {
    console.error('[GRAPH] Measurement log error:', err.message);
    return res.status(500).json({ error: 'Internal error logging measurement.' });
  }

  res.json({ success: true, request_id: trackId });
});

// Graph API measurement batch endpoint — POST variant for high-volume senders
router.post('/api/track', (req, res) => {
  const { access_token, events: eventBatch } = req.body;
  const db = req.db;

  if (!access_token) {
    return res.status(400).json({ error: 'access_token is required.' });
  }

  if (!Array.isArray(eventBatch) || eventBatch.length === 0) {
    return res.status(400).json({ error: 'events array is required and must not be empty.' });
  }

  if (eventBatch.length > 50) {
    return res.status(400).json({ error: 'Maximum 50 events per batch.' });
  }

  const insert = db.prepare(`
    INSERT INTO graph_requests (id, token, url, referrer, pixel_id, ip_address, user_agent, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const insertMany = db.transaction((items) => {
    for (const item of items) {
      insert.run(
        'track_' + uuidv4().replace(/-/g, '').substring(0, 16),
        access_token,
        item.url || null,
        item.referrer || null,
        item.pixel_id || null,
        req.ip,
        req.get('user-agent') || null,
        Date.now()
      );
    }
  });

  try {
    insertMany(eventBatch);
  } catch (err) {
    console.error('[GRAPH] Batch insert error:', err.message);
    return res.status(500).json({ error: 'Batch processing failed.' });
  }

  res.json({ success: true, accepted: eventBatch.length });
});

// Retrieve request history for an authenticated token owner
router.get('/api/requests/:token', (req, res) => {
  const { token } = req.params;
  const db = req.db;
  const sid = req.cookies && req.cookies.sid;

  const session = db.prepare('SELECT * FROM sessions WHERE sid = ? AND expires_at > ?').get(sid, Date.now());
  if (!session) {
    return res.status(401).json({ error: 'Authentication required.' });
  }

  const tokenRecord = db.prepare('SELECT * FROM api_tokens WHERE token = ? AND is_revoked = 0').get(token);
  if (!tokenRecord || tokenRecord.owner_id !== session.user_id) {
    return res.status(403).json({ error: 'Access denied to this token\'s history.' });
  }

  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 50;
  const offset = (page - 1) * limit;

  const requests = db.prepare(`
    SELECT * FROM graph_requests WHERE token = ?
    ORDER BY timestamp DESC LIMIT ? OFFSET ?
  `).all(token, limit, offset);

  const total = db.prepare('SELECT COUNT(*) as c FROM graph_requests WHERE token = ?').get(token).c;

  res.json({ requests, total, page, limit });
});

// Token measurement summary — aggregate stats per access token
router.get('/api/stats', (req, res) => {
  const { access_token } = req.query;
  const db = req.db;
  const sid = req.cookies && req.cookies.sid;

  const session = db.prepare('SELECT * FROM sessions WHERE sid = ? AND expires_at > ?').get(sid, Date.now());
  if (!session) {
    return res.status(401).json({ error: 'Authentication required.' });
  }

  if (!access_token) {
    return res.status(400).json({ error: 'access_token query parameter required.' });
  }

  const tokenRecord = db.prepare('SELECT * FROM api_tokens WHERE token = ? AND owner_id = ?').get(access_token, session.user_id);
  if (!tokenRecord) {
    return res.status(403).json({ error: 'Token not found or access denied.' });
  }

  const stats = db.prepare(`
    SELECT
      COUNT(*) as total_requests,
      COUNT(DISTINCT pixel_id) as unique_pixels,
      MIN(timestamp) as first_request,
      MAX(timestamp) as last_request
    FROM graph_requests WHERE token = ?
  `).get(access_token);

  res.json({ stats, token: access_token });
});

module.exports = router;