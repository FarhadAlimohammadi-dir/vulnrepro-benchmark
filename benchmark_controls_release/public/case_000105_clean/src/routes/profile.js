'use strict';

const express = require('express');
const router = express.Router();
const db = require('../db/database');

function requireAuth(req, res, next) {
  if (!req.session.user) return res.redirect('/auth/login');
  next();
}

// Safe decoy: user-supplied bio is stored and rendered but properly escaped via EJS
router.get('/:username', (req, res) => {
  const username = req.params.username;
  const user = db.prepare('SELECT id, username, email, role, bio, avatar_url, created_at FROM users WHERE username = ?').get(username);
  if (!user) return res.status(404).render('error', { title: 'Not Found', message: 'User not found' });

  const projects = db.prepare(
    'SELECT * FROM projects WHERE owner_id = ? AND status = ? ORDER BY created_at DESC'
  ).all(user.id, 'active');

  res.render('profile', { title: `${user.username}'s Profile`, profileUser: user, projects });
});

router.post('/:username/update', requireAuth, (req, res) => {
  const username = req.params.username;
  if (req.session.user.username !== username && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Access denied' });
  }

  const bio = typeof req.body.bio === 'string' ? req.body.bio.slice(0, 500) : '';
  db.prepare('UPDATE users SET bio = ? WHERE username = ?').run(bio, username);

  db.prepare(
    'INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)'
  ).run(req.session.user.id, 'UPDATE_PROFILE', `profile/${username}`, req.ip);

  res.redirect(`/profile/${username}`);
});

module.exports = router;