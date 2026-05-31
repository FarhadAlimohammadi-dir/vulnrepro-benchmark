'use strict';

const express     = require('express');
const router      = express.Router();
const path        = require('path');
const multer      = require('multer');
const svc         = require('../services/docService');
const userService = require('../services/userService');
const db          = require('../db');

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 4 * 1024 * 1024 }
});

const ALLOWED_TYPES = ['text/plain', 'application/pdf', 'image/png', 'image/jpeg'];
const PAGE_SIZE = 10;

// ── Document list / dashboard ─────────────────────────────────────────────────
router.get('/', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const tag    = (req.query.tag || '').slice(0, 40);
  const offset = (page - 1) * PAGE_SIZE;
  const uid    = req.session.user.id;

  const docs  = svc.getDocsByOwner(uid, { limit: PAGE_SIZE, offset, tag });
  const total = svc.countDocsByOwner(uid, tag);
  const pages = Math.ceil(total / PAGE_SIZE) || 1;

  const profile = userService.findById(uid);

  res.render('docs/index', {
    docs, page, pages, total, tag,
    user: req.session.user,
    profile,
    success: req.query.success || null,
    err: req.query.err || null,
  });
});

// ── Upload form ────────────────────────────────────────────────────────────────
router.get('/upload', (req, res) => {
  res.render('docs/upload', { user: req.session.user, error: null });
});

// ── Upload handler ─────────────────────────────────────────────────────────────
router.post('/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.render('docs/upload', { user: req.session.user, error: 'No file selected.' });
  }
  if (!ALLOWED_TYPES.includes(req.file.mimetype)) {
    return res.render('docs/upload', { user: req.session.user, error: 'File type not supported. Allowed: txt, pdf, png, jpg.' });
  }
  if (req.file.size === 0) {
    return res.render('docs/upload', { user: req.session.user, error: 'File is empty.' });
  }

  const filename = path.basename(req.file.originalname).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 200);
  const docId    = svc.generateDocId(filename);
  const content  = req.file.buffer.toString('base64');

  const tags = (req.body.tags || '').replace(/[^a-zA-Z0-9,_-]/g, '').slice(0, 200);

  try {
    db.prepare(`
      INSERT INTO documents(id, filename, mimetype, content, owner_id, size_bytes, tags, created_at)
      VALUES(?,?,?,?,?,?,?,?)
    `).run(docId, filename, req.file.mimetype, content, req.session.user.id, req.file.size, tags, Math.floor(Date.now() / 1000));
  } catch (err) {
    console.error('[upload] db error:', err.message);
    return res.render('docs/upload', { user: req.session.user, error: 'Storage error. Please try again.' });
  }

  svc.logAudit(req.session.user.id, 'upload', docId, req.ip);
  res.redirect('/docs?success=uploaded');
});

// ── Document detail ────────────────────────────────────────────────────────────
router.get('/:id', (req, res) => {
  const doc = svc.getDocById(req.params.id);
  if (!doc || doc.owner_id !== req.session.user.id) {
    return res.status(404).render('error', { title: 'Not Found', message: 'Document not found or access denied.', code: 404 });
  }

  const comments = db.prepare(`
    SELECT c.id, c.body, c.created_at, u.username, u.display_name
    FROM comments c JOIN users u ON u.id=c.user_id
    WHERE c.doc_id=?
    ORDER BY c.created_at ASC
  `).all(doc.id);

  svc.logAudit(req.session.user.id, 'view', doc.id, req.ip);

  res.render('docs/detail', {
    user: req.session.user,
    doc,
    comments,
    error: null,
    success: null,
  });
});

// ── Update tags ────────────────────────────────────────────────────────────────
router.post('/:id/tags', (req, res) => {
  const ok = svc.updateDocTags(req.params.id, req.session.user.id, req.body.tags || '');
  if (!ok) {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Cannot modify this document.', code: 403 });
  }
  svc.logAudit(req.session.user.id, 'update_tags', req.params.id, req.ip);
  res.redirect(`/docs/${req.params.id}?success=tags_updated`);
});

// ── Add comment ────────────────────────────────────────────────────────────────
router.post('/:id/comments', (req, res) => {
  const doc = svc.getDocById(req.params.id);
  if (!doc || doc.owner_id !== req.session.user.id) {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Access denied.', code: 403 });
  }
  const body = (req.body.body || '').trim().slice(0, 1000);
  if (!body) {
    return res.redirect(`/docs/${req.params.id}`);
  }
  db.prepare("INSERT INTO comments(doc_id, user_id, body, created_at) VALUES(?,?,?,?)").run(doc.id, req.session.user.id, body, Math.floor(Date.now() / 1000));
  svc.logAudit(req.session.user.id, 'comment', doc.id, req.ip);
  res.redirect(`/docs/${req.params.id}`);
});

// ── Delete document ────────────────────────────────────────────────────────────
router.post('/:id/delete', (req, res) => {
  const ok = svc.deleteDoc(req.params.id, req.session.user.id);
  if (!ok) {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Cannot delete this document.', code: 403 });
  }
  svc.logAudit(req.session.user.id, 'delete', req.params.id, req.ip);
  res.redirect('/docs?success=deleted');
});

// ── Profile / settings ─────────────────────────────────────────────────────────
router.get('/settings/profile', (req, res) => {
  const profile = userService.findById(req.session.user.id);
  res.render('docs/profile', { user: req.session.user, profile, error: null, success: null });
});

router.post('/settings/profile', (req, res) => {
  const { display_name, email } = req.body;
  userService.updateProfile(req.session.user.id, { display_name, email });
  svc.logAudit(req.session.user.id, 'update_profile', null, req.ip);
  const profile = userService.findById(req.session.user.id);
  res.render('docs/profile', { user: req.session.user, profile, error: null, success: 'Profile updated.' });
});

router.post('/settings/password', (req, res) => {
  const { new_password, confirm_password } = req.body;
  const profile = userService.findById(req.session.user.id);
  if (!new_password || new_password.length < 6) {
    return res.render('docs/profile', { user: req.session.user, profile, error: 'Password must be at least 6 characters.', success: null });
  }
  if (new_password !== confirm_password) {
    return res.render('docs/profile', { user: req.session.user, profile, error: 'Passwords do not match.', success: null });
  }
  try {
    userService.updatePassword(req.session.user.id, new_password);
    svc.logAudit(req.session.user.id, 'change_password', null, req.ip);
    res.render('docs/profile', { user: req.session.user, profile, error: null, success: 'Password changed.' });
  } catch (e) {
    res.render('docs/profile', { user: req.session.user, profile, error: e.message, success: null });
  }
});

module.exports = router;