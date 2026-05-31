'use strict';
/**
 * User profile and settings routes.
 */
const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { getUserById, updateUserProfile, getExecHistory, getAiSessionsByUser, appendAudit } = require('../db');
const { logger } = require('../logger');

const router = express.Router();

// GET /profile
router.get('/', requireLogin, (req, res) => {
  const user    = getUserById(req.session.userId);
  const history = getExecHistory(req.session.userId, 10);
  const aiSessions = getAiSessionsByUser(req.session.userId);
  res.render('profile', {
    user:       { ...user, role: req.session.role },
    history,
    aiSessions,
    saved: false,
    error: null,
  });
});

// POST /profile — update email / bio
router.post('/', requireLogin, (req, res) => {
  const userId = req.session.userId;
  const { email, bio } = req.body;

  if (!email || !email.includes('@')) {
    const user    = getUserById(userId);
    const history = getExecHistory(userId, 10);
    const aiSessions = getAiSessionsByUser(userId);
    return res.render('profile', {
      user: { ...user, role: req.session.role },
      history,
      aiSessions,
      saved: false,
      error: 'A valid email address is required.',
    });
  }

  updateUserProfile(userId, email.trim(), (bio || '').trim());
  appendAudit(userId, 'profile.update', email.trim(), req.ip);
  logger.info('Profile updated', { userId });

  const user    = getUserById(userId);
  const history = getExecHistory(userId, 10);
  const aiSessions = getAiSessionsByUser(userId);
  res.render('profile', {
    user: { ...user, role: req.session.role },
    history,
    aiSessions,
    saved: true,
    error: null,
  });
});

module.exports = router;