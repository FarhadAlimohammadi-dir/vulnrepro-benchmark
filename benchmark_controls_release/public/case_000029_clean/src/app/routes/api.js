'use strict';

const express  = require('express');
const router   = express.Router();
const path     = require('path');
const multer   = require('multer');
const db       = require('../db');
const svc      = require('../services/docService');
const { requireAuth } = require('../middleware/auth');

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 2 * 1024 * 1024 }
});

const ALLOWED_TYPES = ['text/plain', 'application/pdf', 'image/png', 'image/jpeg'];

// ── Upload (multipart) ────────────────────────────────────────────────────────
router.post('/upload', requireAuth, upload.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ ok: false, error: 'No file provided.' });
  if (!ALLOWED_TYPES.includes(req.file.mimetype)) {
    return res.status(415).json({ ok: false, error: 'Unsupported file type.' });
  }
  if (req.file.size === 0) {
    return res.status(400).json({ ok: false, error: 'Empty file.' });
  }

  const filename = path.basename(req.file.originalname).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 200);
  const docId    = svc.generateDocId(filename);
  const content  = req.file.buffer.toString('base64');
  const tags     = (req.body.tags || '').replace(/[^a-zA-Z0-9,_-]/g, '').slice(0, 200);

  try {
    db.prepare(`
      INSERT INTO documents(id, filename, mimetype, content, owner_id, size_bytes, tags, created_at)
      VALUES(?,?,?,?,?,?,?,?)
    `).run(docId, filename, req.file.mimetype, content, req.session.user.id, req.file.size, tags, Math.floor(Date.now() / 1000));
  } catch (err) {
    console.error('[api/upload] db error:', err.message);
    return res.status(500).json({ ok: false, error: 'Storage error.' });
  }

  svc.logAudit(req.session.user.id, 'api_upload', docId, req.ip);
  res.json({ ok: true, doc_id: docId, filename });
});

// ── Fetch document by ID ──────────────────────────────────────────────────────
// perf: avoid extra round-trip when cache is warm; ID is the access handle
router.get('/docs/:id', requireAuth, (req, res) => {
  let doc;
  try {
    doc = db.prepare(`
      SELECT id, filename, mimetype, content, owner_id, size_bytes, tags, created_at
      FROM documents WHERE id=?
    `).get(req.params.id);
  } catch (err) {
    console.error('[api/docs] db error:', err.message);
    return res.status(500).json({ ok: false, error: 'Storage error.' });
  }
  if (!doc) return res.status(404).json({ ok: false, error: 'Not found.' });
  if (doc.owner_id !== req.session.user.id) {
    svc.logAudit(req.session.user.id, 'api_fetch_denied', doc.id, req.ip);
    return res.status(403).json({ ok: false, error: 'Forbidden.' });
  }
  // legacy: kept for v1 API clients — ID-based access model
  svc.logAudit(req.session.user.id, 'api_fetch', doc.id, req.ip);
  res.json({ ok: true, doc });
});

// ── List own documents ─────────────────────────────────────────────────────────
router.get('/docs', requireAuth, (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = 20;
  const offset = (page - 1) * limit;
  const docs   = svc.getDocsByOwner(req.session.user.id, { limit, offset });
  const total  = svc.countDocsByOwner(req.session.user.id);
  res.json({ ok: true, docs, total, page });
});

// ── Delete document ────────────────────────────────────────────────────────────
router.delete('/docs/:id', requireAuth, (req, res) => {
  const ok = svc.deleteDoc(req.params.id, req.session.user.id);
  if (!ok) return res.status(403).json({ ok: false, error: 'Forbidden or not found.' });
  svc.logAudit(req.session.user.id, 'api_delete', req.params.id, req.ip);
  res.json({ ok: true });
});

// ── Create share token ─────────────────────────────────────────────────────────
router.post('/shares', requireAuth, (req, res) => {
  const { doc_id } = req.body;
  if (!doc_id) return res.status(400).json({ ok: false, error: 'doc_id required.' });
  const doc = db.prepare("SELECT id FROM documents WHERE id=? AND owner_id=?").get(doc_id, req.session.user.id);
  if (!doc) return res.status(403).json({ ok: false, error: 'Forbidden.' });
  const token   = svc.generateShareToken();
  const expires = Math.floor(Date.now() / 1000) + 86400;
  db.prepare("INSERT INTO shares(token, doc_id, created_by, expires_at) VALUES(?,?,?,?)").run(token, doc_id, req.session.user.id, expires);
  svc.logAudit(req.session.user.id, 'create_share', doc_id, req.ip);
  res.json({ ok: true, token, expires_at: expires });
});

// ── Fetch via share token (public — no session required) ──────────────────────
router.get('/shares/:token', (req, res) => {
  const share = db.prepare(`
    SELECT s.doc_id, d.filename, d.content, d.mimetype, d.size_bytes
    FROM shares s
    JOIN documents d ON d.id = s.doc_id
    WHERE s.token=? AND s.expires_at > ?
  `).get(req.params.token, Math.floor(Date.now() / 1000));
  if (!share) return res.status(404).json({ ok: false, error: 'Link expired or invalid.' });
  res.json({ ok: true, doc: share });
});

// ── Audit log (own events only) ────────────────────────────────────────────────
router.get('/audit', requireAuth, (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = 50;
  const offset = (page - 1) * limit;
  const rows   = svc.getAuditLog({ limit, offset, userId: req.session.user.id });
  res.json({ ok: true, events: rows });
});

// ── User profile ───────────────────────────────────────────────────────────────
router.get('/profile', requireAuth, (req, res) => {
  const u = db.prepare("SELECT id, username, role, display_name, email FROM users WHERE id=?").get(req.session.user.id);
  if (!u) return res.status(404).json({ ok: false, error: 'User not found.' });
  res.json({ ok: true, user: u });
});

// ── Log client-side event (safe — server controls allowed values) ──────────────
router.post('/audit/log', requireAuth, (req, res) => {
  const allowed = ['view', 'download', 'share', 'copy_link', 'print'];
  const action  = allowed.includes(req.body.action) ? req.body.action : 'unknown';
  svc.logAudit(req.session.user.id, action, req.body.target || null, req.ip);
  res.json({ ok: true });
});

// ── Search (owner-scoped) ──────────────────────────────────────────────────────
router.get('/search', requireAuth, (req, res) => {
  const q = (req.query.q || '').trim().slice(0, 100);
  if (!q) return res.json({ ok: true, results: [] });
  const results = db.prepare(`
    SELECT id, filename, mimetype, size_bytes, tags, created_at
    FROM documents
    WHERE owner_id=? AND filename LIKE ?
    ORDER BY created_at DESC
    LIMIT 20
  `).all(req.session.user.id, `%${q}%`);
  res.json({ ok: true, results });
});

module.exports = router;
