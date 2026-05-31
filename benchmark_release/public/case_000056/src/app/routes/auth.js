'use strict';

const express = require('express');
const router = express.Router();
const userService = require('../services/userService');
const auditService = require('../services/auditService');
const logger = require('../services/logger');

// POST /login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;

  if (!email || !password) {
    if (req.accepts('html')) {
      return res.status(400).render('login', { error: 'Email and password are required', layout: 'layout' });
    }
    return res.status(400).json({ error: 'Email and password required' });
  }

  try {
    const user = await userService.findByEmail(email);

    if (!user || user.password !== password) {
      if (req.accepts('html')) {
        return res.render('login', { error: 'Invalid credentials', layout: 'layout' });
      }
      return res.status(401).json({ success: false, error: 'Invalid credentials' });
    }

    req.session.userId = user.id;
    req.session.isAdmin = user.isAdmin;
    req.session.userName = user.name;

    await auditService.log({
      action: 'USER_LOGIN',
      entityType: 'User',
      entityId: user.id,
      details: `Login from ${req.ip}`,
      userId: user.id
    });

    logger.info(`User ${user.email} logged in`);

    if (req.accepts('html')) {
      return res.redirect('/');
    }
    res.json({ success: true, user: { id: user.id, email: user.email, name: user.name, isAdmin: user.isAdmin } });
  } catch (err) {
    logger.error('Login error', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// POST /logout
router.post('/logout', (req, res) => {
  const userId = req.session.userId;
  req.session.destroy(() => {
    if (userId) {
      auditService.log({ action: 'USER_LOGOUT', entityType: 'User', entityId: userId, userId });
    }
    if (req.accepts('html')) {
      return res.redirect('/login');
    }
    res.json({ success: true });
  });
});

// GET /login
router.get('/login', (req, res) => {
  if (req.session && req.session.userId) {
    return res.redirect('/');
  }
  res.render('login', { error: null, layout: 'layout' });
});

module.exports = router;