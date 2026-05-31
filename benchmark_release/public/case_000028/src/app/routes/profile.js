'use strict';

const express = require('express');
const router = express.Router();
const { getUserById, updateProfile } = require('../services/userService');
const { record } = require('../services/auditService');

router.get('/', (req, res) => {
  const user = getUserById(req.session.userId);
  if (!user) return res.redirect('/login');
  res.render('profile', { user, saved: false, error: null });
});

router.post('/', (req, res) => {
  const { email, display_name, bio } = req.body;

  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    const user = getUserById(req.session.userId);
    return res.render('profile', { user, saved: false, error: 'Invalid email address.' });
  }

  updateProfile(req.session.userId, {
    email:       (email || '').trim().slice(0, 128),
    displayName: (display_name || '').trim().slice(0, 64),
    bio:         (bio || '').trim().slice(0, 300)
  });

  record({ actorId: req.session.userId, actorName: req.session.username, action: 'UPDATE_PROFILE', resource: `users/${req.session.userId}`, detail: 'Profile updated', ipAddr: req.ip });

  const user = getUserById(req.session.userId);
  res.render('profile', { user, saved: true, error: null });
});

module.exports = router;