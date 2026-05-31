'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth, optionalAuth } = require('../middleware/auth');

router.get('/', optionalAuth, (req, res) => {
  const db = req.db;

  let apps = [];
  let recentEvents = [];

  if (req.user) {
    apps = db.prepare('SELECT * FROM apps WHERE owner_id = ? ORDER BY created_at DESC LIMIT 5').all(req.user.id);
    recentEvents = db.prepare('SELECT * FROM pixel_events ORDER BY timestamp DESC LIMIT 10').all();
  }

  res.render('index', {
    title: 'Meta Pixel Analytics Platform',
    user: req.user,
    apps,
    recentEvents
  });
});

router.get('/dashboard', requireAuth, (req, res) => {
  const db = req.db;
  const user = req.user;

  const apps = db.prepare('SELECT * FROM apps WHERE owner_id = ? ORDER BY created_at DESC').all(user.id);
  const tokenCount = db.prepare('SELECT COUNT(*) as c FROM api_tokens WHERE owner_id = ? AND is_revoked = 0').get(user.id);
  const eventCount = db.prepare(`
    SELECT COUNT(*) as c FROM pixel_events pe
    JOIN apps a ON pe.pixel_id = a.pixel_id
    WHERE a.owner_id = ?
  `).get(user.id);

  const recentActivity = db.prepare(`
    SELECT al.* FROM audit_log al
    WHERE al.actor_id = ?
    ORDER BY al.timestamp DESC LIMIT 8
  `).all(user.id);

  res.render('dashboard', {
    title: 'Dashboard',
    user,
    apps,
    tokenCount: tokenCount.c,
    eventCount: eventCount.c,
    recentActivity
  });
});

router.get('/profile', requireAuth, (req, res) => {
  const db = req.db;
  const user = req.user;
  const apps = db.prepare('SELECT * FROM apps WHERE owner_id = ?').all(user.id);

  res.render('profile', {
    title: 'My Profile',
    user,
    apps,
    success: req.query.saved === '1' ? 'Profile saved successfully.' : null,
    error: null
  });
});

router.post('/profile', requireAuth, (req, res) => {
  const db = req.db;
  const user = req.user;
  const { bio, website, email } = req.body;

  const errors = [];
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.push('Invalid email address format.');
  }
  if (website && website.length > 200) {
    errors.push('Website URL too long.');
  }

  if (errors.length > 0) {
    const apps = db.prepare('SELECT * FROM apps WHERE owner_id = ?').all(user.id);
    return res.render('profile', { title: 'My Profile', user, apps, success: null, error: errors[0] });
  }

  db.prepare('UPDATE users SET bio = ?, website = ?, email = ? WHERE id = ?')
    .run(bio || null, website || null, email || user.email, user.id);

  res.redirect('/profile?saved=1');
});

router.get('/apps', requireAuth, (req, res) => {
  const db = req.db;
  const user = req.user;

  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 10;
  const offset = (page - 1) * limit;
  const search = req.query.q || '';

  let apps, total;
  if (search) {
    apps = db.prepare('SELECT * FROM apps WHERE owner_id = ? AND name LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?')
      .all(user.id, `%${search}%`, limit, offset);
    total = db.prepare('SELECT COUNT(*) as c FROM apps WHERE owner_id = ? AND name LIKE ?')
      .get(user.id, `%${search}%`).c;
  } else {
    apps = db.prepare('SELECT * FROM apps WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?')
      .all(user.id, limit, offset);
    total = db.prepare('SELECT COUNT(*) as c FROM apps WHERE owner_id = ?').get(user.id).c;
  }

  res.render('apps', {
    title: 'My Applications',
    user,
    apps,
    search,
    page,
    totalPages: Math.ceil(total / limit)
  });
});

module.exports = router;