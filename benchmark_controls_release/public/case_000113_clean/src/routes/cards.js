'use strict';

const express = require('express');
const { JSDOM } = require('jsdom');
const DOMPurify = require('dompurify');
const { getDb } = require('../db/database');

const router = express.Router();

function requireLogin(req, res, next) {
  if (!req.session.user) return res.status(401).json({ error: 'Authentication required.' });
  next();
}

function canAccessCard(db, card, user) {
  if (!card) return false;
  if (card.is_public || card.user_id === user.id || user.role === 'admin') return true;
  const share = db.prepare('SELECT id FROM shares WHERE card_id = ? AND shared_with = ?')
    .get(card.id, user.id);
  return !!share;
}

// Owners, admins, and explicitly shared users may read the raw card body.
// Other authenticated viewers of a public card only receive non-sensitive
// metadata via the public preview projection below.
function canReadRawCard(db, card, user) {
  if (!card) return false;
  if (card.user_id === user.id || user.role === 'admin') return true;
  const share = db.prepare('SELECT id FROM shares WHERE card_id = ? AND shared_with = ?')
    .get(card.id, user.id);
  return !!share;
}

function publicCardProjection(card) {
  return {
    id: card.id,
    title: card.title,
    author: card.author,
    is_public: card.is_public,
    template_mode: card.template_mode,
    created_at: card.created_at,
    updated_at: card.updated_at,
  };
}

// Build a DOMPurify instance backed by jsdom
function buildPurifier() {
  const window = new JSDOM('').window;
  return DOMPurify(window);
}

// POST /api/cards — create a new card
router.post('/', requireLogin, (req, res) => {
  const { title, content, is_public, allow_custom_elements, template_mode } = req.body;

  if (!title || !content) {
    return res.status(400).json({ error: 'Title and content are required.' });
  }
  if (title.length > 200) {
    return res.status(400).json({ error: 'Title too long.' });
  }

  const db = getDb();
  const result = db.prepare(`
    INSERT INTO cards (user_id, title, content, is_public, allow_custom_elements, template_mode)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    req.session.user.id,
    title,
    content,
    is_public ? 1 : 0,
    allow_custom_elements ? 1 : 0,
    template_mode ? 1 : 0
  );

  db.prepare(`INSERT INTO audit_log (user_id, action, details, ip) VALUES (?, ?, ?, ?)`)
    .run(req.session.user.id, 'card_create', `id=${result.lastInsertRowid}`, req.ip);

  res.status(201).json({ id: result.lastInsertRowid });
});

// GET /api/cards/:id — fetch a card's raw data
router.get('/:id', requireLogin, (req, res) => {
  const db = getDb();
  const card = db.prepare(`
    SELECT c.*, u.username as author
    FROM cards c JOIN users u ON c.user_id = u.id
    WHERE c.id = ?
  `).get(req.params.id);

  if (!card) return res.status(404).json({ error: 'Card not found.' });

  if (!canAccessCard(db, card, req.session.user)) return res.status(403).json({ error: 'Access denied.' });

  // For public cards, only owners, admins, and explicitly shared users may
  // read the raw content field. Other viewers receive a metadata-only
  // preview so this endpoint cannot be used to bulk-download arbitrary
  // public document bodies.
  if (!canReadRawCard(db, card, req.session.user)) {
    return res.json(publicCardProjection(card));
  }

  res.json(card);
});

// PUT /api/cards/:id — update a card
router.put('/:id', requireLogin, (req, res) => {
  const db = getDb();
  const card = db.prepare('SELECT * FROM cards WHERE id = ?').get(req.params.id);
  if (!card) return res.status(404).json({ error: 'Card not found.' });
  if (card.user_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied.' });
  }

  const { title, content, is_public } = req.body;
  db.prepare(`
    UPDATE cards SET title = ?, content = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `).run(
    title || card.title,
    content || card.content,
    is_public !== undefined ? (is_public ? 1 : 0) : card.is_public,
    card.id
  );

  db.prepare(`INSERT INTO audit_log (user_id, action, details, ip) VALUES (?, ?, ?, ?)`)
    .run(req.session.user.id, 'card_update', `id=${card.id}`, req.ip);

  res.json({ ok: true });
});

// POST /api/cards/:id/comment — add a comment (plain text only)
router.post('/:id/comment', requireLogin, (req, res) => {
  const { body } = req.body;
  if (!body || body.trim().length === 0) {
    return res.status(400).json({ error: 'Comment body required.' });
  }
  // Comments are stored as plain text and escaped in templates
  const safe = String(body).replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const db = getDb();
  const card = db.prepare('SELECT * FROM cards WHERE id = ?').get(req.params.id);
  if (!card) return res.status(404).json({ error: 'Card not found.' });
  if (!canAccessCard(db, card, req.session.user)) return res.status(403).json({ error: 'Access denied.' });

  db.prepare('INSERT INTO comments (card_id, user_id, body) VALUES (?, ?, ?)')
    .run(req.params.id, req.session.user.id, safe);
  res.json({ ok: true });
});

// POST /api/cards/:id/share — share a card with another user
router.post('/:id/share', requireLogin, (req, res) => {
  const { username, permission } = req.body;
  if (!username) return res.status(400).json({ error: 'Username required.' });
  const allowedPerms = ['view', 'edit'];
  const perm = allowedPerms.includes(permission) ? permission : 'view';

  const db = getDb();
  const card = db.prepare('SELECT * FROM cards WHERE id = ?').get(req.params.id);
  if (!card) return res.status(404).json({ error: 'Card not found.' });
  if (card.user_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied.' });
  }

  const target = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (!target) return res.status(404).json({ error: 'User not found.' });

  // Upsert share record
  db.prepare(`
    INSERT INTO shares (card_id, shared_with, permission) VALUES (?, ?, ?)
    ON CONFLICT(card_id, shared_with) DO UPDATE SET permission = excluded.permission
  `).run(card.id, target.id, perm);

  res.json({ ok: true });
});

// POST /api/cards/sanitize — render sanitized HTML for card preview
// Supports custom-element-capable cards and template-safe mode
// perf: avoid extra round-trip when cache is warm
router.post('/sanitize', requireLogin, (req, res) => {
  const { html } = req.body;

  if (typeof html !== 'string') {
    return res.status(400).json({ error: 'html field required.' });
  }

  // Build per-request purifier (jsdom window is stateful)
  const purify = buildPurifier();

  // Single conservative config: strict tag/attribute allow-list, no custom
  // elements, template expressions stripped. The flags previously read from
  // the request body (allow_custom_elements / template_mode) were creator-
  // controlled and could be flipped per card by a low-privilege author, so
  // they are no longer honored.
  const config = {
    ALLOWED_TAGS: [
      'a', 'p', 'br', 'hr', 'span', 'div', 'strong', 'em', 'b', 'i', 'u',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
      'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ],
    ALLOWED_ATTR: ['href', 'title', 'class', 'colspan', 'rowspan'],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tel:|#|\/)/i,
    FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed', 'math', 'svg', 'link', 'meta', 'base'],
    FORBID_ATTR: ['style', 'srcset', 'xlink:href', 'formaction', 'action'],
    ALLOW_DATA_ATTR: false,
    SAFE_FOR_TEMPLATES: true,
  };

  const sanitized = purify.sanitize(html, config);

  res.json({ sanitized });
});

module.exports = router;
