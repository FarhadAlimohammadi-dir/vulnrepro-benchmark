'use strict';

const express = require('express');
const { requireAuth } = require('../middleware/auth');
const imageSvc  = require('../services/imageService');
const audit     = require('../services/auditService');
const { getDb } = require('../db');

const router = express.Router();

// ── Dashboard / my images ─────────────────────────────────────────────────────
router.get('/dashboard', requireAuth, (req, res) => {
  const page   = parseInt(req.query.page, 10) || 1;
  const search = (req.query.q || '').trim();
  const result = imageSvc.listForUser(req.session.userId, page, search);

  const db          = getDb();
  const collections = db.prepare('SELECT * FROM collections WHERE owner_id = ? ORDER BY name').all(req.session.userId);
  const sharedWith  = db.prepare(`
    SELECT i.*, u.username AS owner_name
    FROM shares s
    JOIN images i ON i.id = s.image_id
    JOIN users u  ON u.id = i.owner_id
    WHERE s.shared_with = ?
    ORDER BY s.created_at DESC
    LIMIT 5
  `).all(req.session.userId);

  res.render('dashboard', {
    images:      result.rows,
    total:       result.total,
    page:        result.page,
    pages:       result.pages,
    search,
    collections,
    sharedWith
  });
});

// ── Public gallery ────────────────────────────────────────────────────────────
router.get('/gallery', (req, res) => {
  const page   = parseInt(req.query.page, 10) || 1;
  const search = (req.query.q || '').trim();
  const result = imageSvc.publicGallery(page, search);

  res.render('gallery', {
    images: result.rows,
    total:  result.total,
    page:   result.page,
    pages:  result.pages,
    search
  });
});

// ── User profile ──────────────────────────────────────────────────────────────
router.get('/profile/:username', (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT id, username, full_name, bio, plan, created_at FROM users WHERE username = ?')
                 .get(req.params.username);
  if (!user) return res.status(404).render('error', { code: 404, message: 'User not found.' });

  const images = db.prepare(`
    SELECT * FROM images WHERE owner_id = ? AND is_public = 1 ORDER BY created_at DESC LIMIT 20
  `).all(user.id);

  res.render('profile', { profileUser: user, images });
});

// ── Settings ──────────────────────────────────────────────────────────────────
router.get('/settings', requireAuth, (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.userId);
  res.render('settings', { user, saved: !!req.query.saved, error: null });
});

router.post('/settings', requireAuth, (req, res) => {
  const { full_name, email, bio } = req.body;
  const db = getDb();

  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.userId);
    return res.render('settings', { user, saved: false, error: 'Please enter a valid email address.' });
  }

  db.prepare(`
    UPDATE users SET full_name = ?, email = ?, bio = ?, updated_at = datetime('now') WHERE id = ?
  `).run(full_name || null, email || null, bio || null, req.session.userId);

  audit.record(req.session.userId, 'settings_update', 'user', req.session.userId, 'Profile updated', req.ip);
  res.redirect('/settings?saved=1');
});

module.exports = router;