'use strict';

const express   = require('express');
const { requireAuth } = require('../middleware/auth');
const imageSvc  = require('../services/imageService');
const engine    = require('../services/analysisEngine');
const audit     = require('../services/auditService');
const { getDb } = require('../db');
const logger    = require('../services/logger');

const router = express.Router();

// ── Upload ────────────────────────────────────────────────────────────────────
router.post('/images/upload', requireAuth, (req, res) => {
  const { filename, content_type, description, tags, is_public, file_size } = req.body;
  try {
    const result = imageSvc.createImage({
      ownerId:     req.session.userId,
      filename,
      contentType: content_type,
      description,
      tags,
      fileSize:    file_size || 0,
      isPublic:    is_public === 'true' || is_public === true || is_public === 1
    });
    audit.record(req.session.userId, 'upload', 'image', result.id, `Uploaded ${filename}`, req.ip);
    logger.info(`Upload: user=${req.session.userId} file=${filename} id=${result.id}`);
    res.status(201).json({ id: result.id, storage_path: result.storage_path });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// ── Get image metadata — ownership enforced ───────────────────────────────────
router.get('/images/:id/meta', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (img.owner_id !== req.session.userId) {
    audit.record(req.session.userId, 'meta_denied', 'image', img.id,
      `User ${req.session.userId} attempted to access image ${img.id} owned by ${img.owner_id}`, req.ip);
    return res.status(403).json({ error: 'Forbidden.' });
  }
  res.json({
    id:           img.id,
    filename:     img.filename,
    content_type: img.content_type,
    tags:         img.tags,
    file_size:    img.file_size,
    is_public:    !!img.is_public,
    created_at:   img.created_at,
    storage_path: img.storage_path
  });
});

// ── Update image metadata — ownership enforced ────────────────────────────────
router.patch('/images/:id', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (img.owner_id !== req.session.userId) return res.status(403).json({ error: 'Forbidden.' });

  const { tags, description, is_public } = req.body;
  const db = getDb();
  db.prepare(`
    UPDATE images SET
      tags          = COALESCE(?, tags),
      ai_description = COALESCE(?, ai_description),
      is_public     = COALESCE(?, is_public),
      updated_at    = datetime('now')
    WHERE id = ?
  `).run(tags || null, description || null, is_public != null ? (is_public ? 1 : 0) : null, img.id);

  audit.record(req.session.userId, 'update', 'image', img.id, 'Image metadata updated', req.ip);
  res.json({ status: 'updated', id: img.id });
});

// ── Share image — ownership enforced ─────────────────────────────────────────
router.post('/images/:id/share', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (img.owner_id !== req.session.userId) return res.status(403).json({ error: 'Forbidden.' });

  const { target_username } = req.body;
  if (!target_username) return res.status(400).json({ error: 'target_username required.' });

  const db     = getDb();
  const target = db.prepare('SELECT id FROM users WHERE username = ?').get(target_username);
  if (!target) return res.status(404).json({ error: 'Target user not found.' });

  db.prepare('INSERT OR IGNORE INTO shares (image_id, shared_with) VALUES (?, ?)').run(img.id, target.id);
  audit.record(req.session.userId, 'share', 'image', img.id,
    `Shared image ${img.id} with user ${target_username}`, req.ip);
  res.json({ status: 'shared', image_id: img.id, shared_with: target_username });
});

// ── Delete image — ownership enforced ─────────────────────────────────────────
router.delete('/images/:id', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (img.owner_id !== req.session.userId) {
    audit.record(req.session.userId, 'delete_denied', 'image', img.id,
      `User ${req.session.userId} tried to delete image ${img.id} owned by ${img.owner_id}`, req.ip);
    return res.status(403).json({ error: 'Forbidden.' });
  }
  imageSvc.deleteImage(img.id);
  audit.record(req.session.userId, 'delete', 'image', img.id, `Deleted image ${img.filename}`, req.ip);
  res.json({ status: 'deleted', id: img.id });
});

// ── Get comments for an image (public images only, or owner) ─────────────────
router.get('/images/:id/comments', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (!img.is_public && img.owner_id !== req.session.userId) {
    return res.status(403).json({ error: 'Forbidden.' });
  }
  const db       = getDb();
  const comments = db.prepare(`
    SELECT c.id, c.body, c.created_at, u.username
    FROM comments c JOIN users u ON u.id = c.user_id
    WHERE c.image_id = ? ORDER BY c.created_at ASC
  `).all(img.id);
  res.json({ comments });
});

// ── Post a comment ────────────────────────────────────────────────────────────
router.post('/images/:id/comments', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (!img.is_public && img.owner_id !== req.session.userId) {
    return res.status(403).json({ error: 'Forbidden.' });
  }
  const { body } = req.body;
  if (!body || !body.trim()) return res.status(400).json({ error: 'Comment body is required.' });

  const db   = getDb();
  const info = db.prepare('INSERT INTO comments (image_id, user_id, body) VALUES (?, ?, ?)').run(
    img.id, req.session.userId, body.trim()
  );
  res.status(201).json({ id: info.lastInsertRowid, status: 'created' });
});

// ── Tag suggestions ───────────────────────────────────────────────────────────
router.get('/tags/suggest', requireAuth, (req, res) => {
  const contentType = req.query.content_type || '';
  const suggestions = engine.suggestTags(contentType);
  res.json({ suggestions });
});

// ── AI analysis pipeline endpoint ─────────────────────────────────────────────
// Accepts a storage_path (as returned by /api/images/upload) and runs the
// analysis engine against the stored record.
//
// legacy: kept for v1 API clients that track images by storage path rather
// than by numeric ID.  The v2 flow uses POST /api/images/:id/analyze instead.
router.post('/analyze', requireAuth, (req, res) => {
  const { storage_path } = req.body;
  if (!storage_path) {
    return res.status(400).json({ error: 'storage_path is required.' });
  }

  // Authorize BEFORE running analysis: only the owner may resolve a
  // storage_path. This prevents the analysis engine from being used as an
  // oracle that returns private metadata for objects the caller does not own.
  const db = getDb();
  const own = db.prepare(
    'SELECT id FROM images WHERE storage_path = ? AND owner_id = ?'
  ).get(storage_path, req.session.userId);
  if (!own) {
    return res.status(404).json({ error: 'No image record found for the given storage path.' });
  }

  const result = engine.runAnalysis(storage_path);
  if (!result.found) {
    return res.status(404).json({ error: 'No image record found for the given storage path.' });
  }
  if (result.ownerId !== req.session.userId) {
    return res.status(403).json({ error: 'Forbidden.' });
  }

  audit.record(
    req.session.userId, 'analyze', 'image', result.imageId,
    `Analysis requested for storage path ${storage_path}`, req.ip
  );
  logger.info(`Analyze: user=${req.session.userId} path=${storage_path} imageId=${result.imageId}`);

  res.json({
    storage_path,
    filename: result.filename,
    analysis: {
      description: result.description,
      tags:        result.tags,
      ocr_text:    result.ocr_text
    }
  });
});

// ── v2 per-ID analysis endpoint (ownership enforced) ─────────────────────────
router.post('/images/:id/analyze', requireAuth, (req, res) => {
  const img = imageSvc.getById(req.params.id);
  if (!img) return res.status(404).json({ error: 'Image not found.' });
  if (img.owner_id !== req.session.userId) return res.status(403).json({ error: 'Forbidden.' });

  const result = engine.runAnalysis(img.storage_path);
  audit.record(req.session.userId, 'analyze', 'image', img.id,
    `v2 analysis for image ${img.id}`, req.ip);
  res.json({
    storage_path: img.storage_path,
    filename:     img.filename,
    analysis: {
      description: result.description,
      tags:        result.tags,
      ocr_text:    result.ocr_text
    }
  });
});

// ── Batch status check — SRE-2031: batches up to 50 items ────────────────────
router.post('/images/batch-status', requireAuth, (req, res) => {
  const { ids } = req.body;
  if (!Array.isArray(ids) || ids.length === 0) {
    return res.status(400).json({ error: 'ids must be a non-empty array.' });
  }
  const limited = ids.slice(0, 50);
  const db      = getDb();
  const rows    = limited.map(id => {
    const img = db.prepare('SELECT id, owner_id, filename, ai_description, created_at FROM images WHERE id = ?').get(id);
    if (!img || img.owner_id !== req.session.userId) return { id, status: 'not_found' };
    return { id: img.id, filename: img.filename, status: img.ai_description ? 'complete' : 'pending' };
  });
  res.json({ results: rows });
});

module.exports = router;
