'use strict';

const express = require('express');
const router = express.Router();
const userService = require('../services/userService');
const auditService = require('../services/auditService');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { validatePagination } = require('../middleware/validate');
const logger = require('../services/logger');

// GET /api/users/profile — authenticated user's own profile
router.get('/profile', requireAuth, async (req, res) => {
  try {
    const user = await userService.findById(req.session.userId);
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json(user);
  } catch (err) {
    logger.error('Error fetching profile', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// PUT /api/users/profile — update own profile fields
router.put('/profile', requireAuth, async (req, res) => {
  try {
    const { name, bio, avatarUrl } = req.body;
    const updated = await userService.updateProfile(req.session.userId, { name, bio, avatarUrl });

    await auditService.log({
      action: 'USER_PROFILE_UPDATED',
      entityType: 'User',
      entityId: req.session.userId,
      details: 'Profile updated',
      userId: req.session.userId
    });

    res.json(updated);
  } catch (err) {
    logger.error('Error updating profile', err);
    res.status(500).json({ error: 'Failed to update profile' });
  }
});

// GET /api/users/:id/public — public author profile
router.get('/:id(\\d+)/public', async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const profile = await userService.getPublicProfile(id);
    if (!profile) return res.status(404).json({ error: 'User not found' });
    res.json(profile);
  } catch (err) {
    logger.error('Error fetching public profile', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/users — admin: list all users with pagination
router.get('/', requireAdmin, validatePagination, async (req, res) => {
  try {
    const { page, pageSize } = req.pagination;
    const result = await userService.listAll({ page, pageSize });
    res.json(result);
  } catch (err) {
    logger.error('Error listing users', err);
    res.status(500).json({ error: 'Failed to list users' });
  }
});

// GET /api/users/settings — user account settings
router.get('/settings', requireAuth, async (req, res) => {
  try {
    const user = await userService.findById(req.session.userId);
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json({
      id: user.id,
      email: user.email,
      name: user.name,
      notifications: {
        emailOnComment: true,
        emailOnPublish: false,
        weeklyDigest: true
      },
      theme: 'system',
      language: 'en'
    });
  } catch (err) {
    logger.error('Error fetching settings', err);
    res.status(500).json({ error: 'Server error' });
  }
});

module.exports = router;