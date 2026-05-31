'use strict';

const express              = require('express');
const { db }               = require('../db');
const { requireAuth }      = require('../middleware/auth');
const { auditMiddleware, writeAudit } = require('../middleware/audit');
const { TOOLS, parseDirectives, runToolChain } = require('../services/toolEngine');

const router = express.Router();
router.use(requireAuth);
router.use(auditMiddleware);

// ── POST /api/assistant/chat ─────────────────────────────────────
// Primary assistant interaction endpoint. Accepts a free-form message,
// parses any embedded tool directives, and runs the resulting chain.
router.post('/assistant/chat', (req, res) => {
  const { message } = req.body;
  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'Message is required' });
  }
  if (message.length > 4000) {
    return res.status(400).json({ error: 'Message too long (max 4000 chars)' });
  }

  const uid = req.session.userId;

  const directives   = parseDirectives(message);
  const toolResults  = [];
  const pendingTools = directives.map(d => d.tool).filter(Boolean);

  const reply = toolResults.length > 0
    ? `Completed ${toolResults.length} action(s) on your behalf.`
    : pendingTools.length > 0
    ? `Queued ${pendingTools.length} action(s) for confirmation.`
    : 'How can I help you today?';

  db.prepare(
    'INSERT INTO conversations (user_id,message,reply,created_at) VALUES (?,?,?,?)'
  ).run(uid, message, reply, Date.now());

  res.json({ reply, tool_results: toolResults, pending_tools: pendingTools });
});

// ── GET /api/calls ───────────────────────────────────────────────
// Returns the authenticated user's call history.
router.get('/calls', (req, res) => {
  const rows = db.prepare(
    'SELECT id,dial_string,status,placed_at FROM call_log WHERE user_id=? ORDER BY placed_at DESC LIMIT 50'
  ).all(req.session.userId);
  res.json({ calls: rows });
});

// ── GET /api/notifications ───────────────────────────────────────
// Returns unread notification items for display in the UI.
router.get('/notifications', (req, res) => {
  const rows = db.prepare(
    'SELECT id,app_name,body,priority,read,created_at FROM notifications WHERE user_id=? ORDER BY created_at DESC'
  ).all(req.session.userId);
  res.json({ notifications: rows });
});

// ── POST /api/notifications/:id/read ────────────────────────────
router.post('/notifications/:id/read', (req, res) => {
  db.prepare('UPDATE notifications SET read=1 WHERE user_id=? AND id=?').run(
    req.session.userId, req.params.id
  );
  res.json({ status: 'ok' });
});

// ── POST /api/tools/sms ─────────────────────────────────────────
// Standalone SMS dispatch — always requests confirmation first.
router.post('/tools/sms', (req, res) => {
  const { to, body, confirmed } = req.body;
  if (!to || !body) return res.status(400).json({ error: 'to and body are required' });
  if (!/^\+?[\d\s\-().]{7,20}$/.test(to)) {
    return res.status(400).json({ error: 'Invalid phone number format' });
  }
  const result = TOOLS.sms.run(req.session.userId, { to, body }, !!confirmed);
  res.json(result);
});

// ── POST /api/tools/calendar ────────────────────────────────────
// Standalone calendar event creation with full validation.
router.post('/tools/calendar', (req, res) => {
  const { title, date, description } = req.body;
  if (!title || !date) return res.status(400).json({ error: 'title and date are required' });
  const result = TOOLS.calendar.run(req.session.userId, { title, date, description });
  res.json(result);
});

// ── GET /api/tools/contacts ──────────────────────────────────────
// Contact quick-search for the assistant's autocomplete.
router.get('/tools/contacts', (req, res) => {
  const q = (req.query.q || '').slice(0, 60);
  if (!q) return res.json({ contacts: [] });
  const result = TOOLS.contacts_search.run(req.session.userId, { query: q });
  res.json(result);
});

// ── GET /api/conversations ───────────────────────────────────────
// Paginated conversation history for the current user.
router.get('/conversations', (req, res) => {
  const page    = Math.max(1, parseInt(req.query.page, 10) || 1);
  const perPage = 20;
  const offset  = (page - 1) * perPage;
  const uid     = req.session.userId;
  const rows    = db.prepare('SELECT id,message,reply,created_at FROM conversations WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?').all(uid, perPage, offset);
  const total   = db.prepare('SELECT COUNT(*) as c FROM conversations WHERE user_id=?').get(uid).c;
  res.json({ conversations: rows, total, page, perPage });
});

// ── DELETE /api/conversations/:id ───────────────────────────────
router.delete('/conversations/:id', (req, res) => {
  db.prepare('DELETE FROM conversations WHERE user_id=? AND id=?').run(req.session.userId, req.params.id);
  res.json({ status: 'deleted' });
});

module.exports = router;
