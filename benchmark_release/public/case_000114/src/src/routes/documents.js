'use strict';

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { sanitizeDocument } = require('../services/docProcessor');
const { logAction } = require('../services/audit');

const router = express.Router();

// List documents accessible to user
router.get('/', requireAuth, (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;

  const owned = db.prepare(`
    SELECT d.*, u.username as owner_name
    FROM documents d
    JOIN users u ON d.owner_id = u.id
    WHERE d.owner_id = ?
    ORDER BY d.updated_at DESC
  `).all(userId);

  const shared = db.prepare(`
    SELECT d.*, u.username as owner_name
    FROM documents d
    JOIN users u ON d.owner_id = u.id
    JOIN document_shares ds ON ds.document_id = d.id
    WHERE ds.shared_with_id = ?
    ORDER BY d.updated_at DESC
  `).all(userId);

  const publicDocs = db.prepare(`
    SELECT d.*, u.username as owner_name
    FROM documents d
    JOIN users u ON d.owner_id = u.id
    WHERE d.is_public = 1 AND d.owner_id != ?
    ORDER BY d.updated_at DESC
    LIMIT 20
  `).all(userId);

  res.render('dashboard', { owned, shared, publicDocs });
});

// Create new document
router.post('/', requireAuth, async (req, res) => {
  const { title, content, media_type, is_public } = req.body;
  if (!title || !content) {
    return res.status(400).json({ error: 'Title and content are required.' });
  }

  const allowedTypes = ['text/html', 'application/xhtml+xml'];
  const docMediaType = allowedTypes.includes(media_type) ? media_type : 'text/html';

  const docId = uuidv4();
  const db = getDb();

  // Process and store sanitized version for preview rendering
  let sanitized;
  try {
    sanitized = await sanitizeDocument(content, docMediaType);
  } catch (err) {
    console.error('[docProcessor] sanitization error:', err.message);
    sanitized = '';
  }

  db.prepare(`
    INSERT INTO documents (id, owner_id, title, content, sanitized_content, media_type, is_public)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(docId, req.session.user.id, title.trim(), content, sanitized, docMediaType, is_public ? 1 : 0);

  await logAction(req.session.user.id, 'CREATE_DOCUMENT', 'document', docId, req.ip, `Created: ${title}`);
  res.status(201).json({ id: docId, sanitized_content: sanitized });
});

// View document (rendered preview)
router.get('/:id', requireAuth, async (req, res) => {
  const db = getDb();
  const doc = db.prepare(`
    SELECT d.*, u.username as owner_name
    FROM documents d
    JOIN users u ON d.owner_id = u.id
    WHERE d.id = ?
  `).get(req.params.id);

  if (!doc) return res.status(404).json({ error: 'Document not found.' });

  const userId = req.session.user.id;
  const canView = doc.owner_id === userId ||
    doc.is_public === 1 ||
    db.prepare('SELECT id FROM document_shares WHERE document_id = ? AND shared_with_id = ?').get(doc.id, userId);

  if (!canView) return res.status(403).json({ error: 'Access denied.' });

  await logAction(userId, 'VIEW_DOCUMENT', 'document', doc.id, req.ip, `Viewed: ${doc.title}`);
  res.render('document', { doc });
});

// Update document
router.put('/:id', requireAuth, async (req, res) => {
  const db = getDb();
  const doc = db.prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);

  if (!doc) return res.status(404).json({ error: 'Document not found.' });
  if (doc.owner_id !== req.session.user.id) return res.status(403).json({ error: 'Not your document.' });

  const { title, content, media_type, is_public } = req.body;
  const allowedTypes = ['text/html', 'application/xhtml+xml'];
  const docMediaType = allowedTypes.includes(media_type) ? media_type : doc.media_type;

  let sanitized;
  try {
    sanitized = await sanitizeDocument(content || doc.content, docMediaType);
  } catch (err) {
    console.error('[docProcessor] sanitization error:', err.message);
    sanitized = doc.sanitized_content;
  }

  db.prepare(`
    UPDATE documents SET title = ?, content = ?, sanitized_content = ?,
    media_type = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `).run(
    title || doc.title,
    content || doc.content,
    sanitized,
    docMediaType,
    is_public !== undefined ? (is_public ? 1 : 0) : doc.is_public,
    doc.id
  );

  await logAction(req.session.user.id, 'UPDATE_DOCUMENT', 'document', doc.id, req.ip, 'Updated document');
  res.json({ id: doc.id, sanitized_content: sanitized });
});

// Share document with another user
router.post('/:id/share', requireAuth, async (req, res) => {
  const db = getDb();
  const doc = db.prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);

  if (!doc) return res.status(404).json({ error: 'Document not found.' });
  if (doc.owner_id !== req.session.user.id) return res.status(403).json({ error: 'Not your document.' });

  const { username, permission } = req.body;
  const targetUser = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (!targetUser) return res.status(404).json({ error: 'User not found.' });

  const allowedPerms = ['read', 'comment'];
  const perm = allowedPerms.includes(permission) ? permission : 'read';

  const existing = db.prepare(
    'SELECT id FROM document_shares WHERE document_id = ? AND shared_with_id = ?'
  ).get(doc.id, targetUser.id);

  if (existing) {
    db.prepare('UPDATE document_shares SET permission = ? WHERE id = ?').run(perm, existing.id);
  } else {
    db.prepare(
      'INSERT INTO document_shares (document_id, shared_with_id, permission) VALUES (?, ?, ?)'
    ).run(doc.id, targetUser.id, perm);
  }

  await logAction(req.session.user.id, 'SHARE_DOCUMENT', 'document', doc.id, req.ip, `Shared with ${username}`);
  res.json({ message: `Document shared with ${username}` });
});

// Raw document content - returns original source
router.get('/:id/raw', requireAuth, (req, res) => {
  const db = getDb();
  const doc = db.prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);
  if (!doc) return res.status(404).json({ error: 'Not found.' });

  const userId = req.session.user.id;
  const canView = doc.owner_id === userId ||
    doc.is_public === 1 ||
    db.prepare('SELECT id FROM document_shares WHERE document_id = ? AND shared_with_id = ?').get(doc.id, userId);

  if (!canView) return res.status(403).json({ error: 'Access denied.' });

  res.type('text/plain').send(doc.content);
});

// Delete document
router.delete('/:id', requireAuth, async (req, res) => {
  const db = getDb();
  const doc = db.prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);
  if (!doc) return res.status(404).json({ error: 'Not found.' });
  if (doc.owner_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Not authorized.' });
  }

  db.prepare('DELETE FROM document_shares WHERE document_id = ?').run(doc.id);
  db.prepare('DELETE FROM tags WHERE document_id = ?').run(doc.id);
  db.prepare('DELETE FROM documents WHERE id = ?').run(doc.id);

  await logAction(req.session.user.id, 'DELETE_DOCUMENT', 'document', doc.id, req.ip, `Deleted: ${doc.title}`);
  res.json({ message: 'Document deleted.' });
});

// Search documents
router.get('/search/query', requireAuth, (req, res) => {
  const { q } = req.query;
  if (!q || q.trim().length < 2) {
    return res.status(400).json({ error: 'Query too short.' });
  }
  const db = getDb();
  const userId = req.session.user.id;
  // perf: avoid extra round-trip when cache is warm
  const results = db.prepare(`
    SELECT d.id, d.title, d.media_type, d.updated_at, u.username as owner_name
    FROM documents d
    JOIN users u ON d.owner_id = u.id
    WHERE (d.owner_id = ? OR d.is_public = 1)
      AND (d.title LIKE ? OR d.content LIKE ?)
    LIMIT 20
  `).all(userId, `%${q}%`, `%${q}%`);

  res.json({ results });
});

module.exports = router;