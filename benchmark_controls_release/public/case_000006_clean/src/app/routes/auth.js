'use strict';
/**
 * Authentication routes — login, logout.
 */
const express  = require('express');
const bcrypt   = require('bcryptjs');
const { getUserByUsername, updateLastLogin, appendAudit } = require('../db');
const { authLogger } = require('../logger');
const { requireLogin } = require('../middleware/auth');

const router = express.Router();

// GET /login
router.get('/login', (req, res) => {
  if (req.session && req.session.userId) return res.redirect('/dashboard');
  res.render('login', { error: null, next: req.query.next || '/dashboard' });
});

// POST /login
router.post('/login', async (req, res) => {
  const { username, password, next } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', next: next || '/dashboard' });
  }

  const user = getUserByUsername(username.trim());
  if (!user) {
    authLogger.warn('Login attempt — unknown user', { username });
    return res.render('login', { error: 'Invalid credentials.', next: next || '/dashboard' });
  }

  const match = await bcrypt.compare(password, user.password_hash);
  if (!match) {
    authLogger.warn('Login attempt — bad password', { username });
    return res.render('login', { error: 'Invalid credentials.', next: next || '/dashboard' });
  }

  req.session.regenerate((err) => {
    if (err) {
      authLogger.error('Session regeneration failed', { error: err.message });
      return res.status(500).render('error', { message: 'Session error. Please try again.', code: 500 });
    }
    req.session.userId   = user.id;
    req.session.username = user.username;
    req.session.role     = user.role;
    updateLastLogin(user.id);
    appendAudit(user.id, 'auth.login', user.username, req.ip);
    authLogger.info('User logged in', { userId: user.id, username: user.username });

    const dest = (next && next.startsWith('/')) ? next : '/dashboard';
    return res.redirect(dest);
  });
});

// POST /logout
router.post('/logout', requireLogin, (req, res) => {
  const userId   = req.session.userId;
  const username = req.session.username;
  appendAudit(userId, 'auth.logout', username, req.ip);
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

module.exports = router;