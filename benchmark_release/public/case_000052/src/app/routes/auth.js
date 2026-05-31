'use strict';

const express = require('express');
const router = express.Router();
const logger = require('../services/logger');
const { requireLogin, auditLog } = require('../middleware/auth');

// GET /login
router.get('/login', (req, res) => {
  if (req.session.user) {
    return res.redirect(req.query.next || '/');
  }
  res.render('login', {
    user: null,
    error: null,
    next: req.query.next || '/',
    page: 'login'
  });
});

// POST /login
router.post('/login', (req, res) => {
  const { username, password, next } = req.body;
  const returnTo = next || '/';

  if (!username || !password) {
    return res.render('login', {
      user: null,
      error: 'Username and password are required.',
      next: returnTo,
      page: 'login'
    });
  }

  const user = req.db.prepare(
    'SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1'
  ).get(username.trim(), password);

  if (!user) {
    logger.warn(`Failed login attempt for username: ${username}`);
    return res.render('login', {
      user: null,
      error: 'Invalid credentials. Please try again.',
      next: returnTo,
      page: 'login'
    });
  }

  req.session.user = user.username;
  req.session.userId = user.id;
  req.session.userRole = user.role;

  // Update last login
  req.db.prepare('UPDATE users SET last_login = strftime(\'%s\', \'now\') WHERE id = ?').run(user.id);

  // Audit
  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, ip_address, user_agent, details)
    VALUES (?, 'user.login', 'session', ?, ?, ?)
  `).run(user.id, req.ip, req.headers['user-agent'] || '', `Login from ${req.ip}`);

  logger.info(`User ${user.username} logged in`);

  // Validate redirect target
  let destination = returnTo;
  if (!destination.startsWith('/') || destination.startsWith('//')) {
    destination = '/';
  }

  res.redirect(destination);
});

// GET /logout
router.get('/logout', (req, res) => {
  const userId = req.session.userId;
  const username = req.session.user;
  req.session.destroy(err => {
    if (err) logger.warn(`Session destroy error: ${err.message}`);
    if (userId) {
      try {
        req.db.prepare(`
          INSERT INTO audit_log (user_id, action, resource_type, details)
          VALUES (?, 'user.logout', 'session', ?)
        `).run(userId, `User ${username} logged out`);
      } catch (e) {
        // ignore
      }
    }
    res.redirect('/');
  });
});

// GET /profile
router.get('/profile', requireLogin, (req, res) => {
  const user = req.db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.userId);
  const tokens = req.db.prepare(`
    SELECT at.token, at.scope, at.issued_at, at.expires_at, oc.name as client_name
    FROM access_tokens at
    LEFT JOIN oauth_clients oc ON at.client_id = oc.id
    WHERE at.user_id = ? AND at.is_revoked = 0
    ORDER BY at.issued_at DESC
    LIMIT 10
  `).all(req.session.userId);

  const consents = req.db.prepare(`
    SELECT uc.*, oc.name as client_name, oc.website
    FROM user_consents uc
    JOIN oauth_clients oc ON uc.client_id = oc.id
    WHERE uc.user_id = ?
  `).all(req.session.userId);

  res.render('profile', {
    user: req.session.user,
    userRecord: user,
    tokens,
    consents,
    page: 'profile'
  });
});

// POST /profile — update bio/name
router.post('/profile', requireLogin, (req, res) => {
  const { full_name, bio } = req.body;

  if (full_name && full_name.length > 100) {
    return res.status(400).render('error', {
      user: req.session.user,
      title: 'Validation Error',
      message: 'Full name must not exceed 100 characters.',
      code: 400
    });
  }

  req.db.prepare('UPDATE users SET full_name = ?, bio = ? WHERE id = ?').run(
    (full_name || '').trim(),
    (bio || '').trim().slice(0, 500),
    req.session.userId
  );

  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
    VALUES (?, 'user.profile_update', 'user', ?, 'Profile updated via web UI')
  `).run(req.session.userId, req.session.userId);

  res.redirect('/profile');
});

// GET /profile/:id — public profile
router.get('/profile/:id', (req, res) => {
  const user = req.db.prepare(
    'SELECT id, username, full_name, bio, role, created_at FROM users WHERE id = ? AND is_active = 1'
  ).get(req.params.id);

  if (!user) {
    return res.status(404).render('error', {
      user: req.session.user || null,
      title: 'User Not Found',
      message: 'The user profile you requested does not exist.',
      code: 404
    });
  }

  res.render('user_profile', {
    user: req.session.user || null,
    profile: user,
    page: 'users'
  });
});

// POST /revoke-token
router.post('/revoke-token', requireLogin, (req, res) => {
  const { token } = req.body;
  if (!token) {
    return res.status(400).json({ error: 'token_required' });
  }

  const record = req.db.prepare(
    'SELECT * FROM access_tokens WHERE token = ? AND user_id = ?'
  ).get(token, req.session.userId);

  if (!record) {
    return res.status(404).json({ error: 'token_not_found' });
  }

  req.db.prepare('UPDATE access_tokens SET is_revoked = 1 WHERE token = ?').run(token);

  req.db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, details)
    VALUES (?, 'token.revoked', 'access_token', 'User manually revoked token')
  `).run(req.session.userId);

  res.redirect('/profile');
});

// POST /revoke-consent
router.post('/revoke-consent', requireLogin, (req, res) => {
  const { client_id } = req.body;

  req.db.prepare(
    'DELETE FROM user_consents WHERE user_id = ? AND client_id = ?'
  ).run(req.session.userId, client_id);

  // Also revoke active tokens for this client
  req.db.prepare(
    'UPDATE access_tokens SET is_revoked = 1 WHERE user_id = ? AND client_id = ?'
  ).run(req.session.userId, client_id);

  logger.info(`User ${req.session.user} revoked consent for client ${client_id}`);
  res.redirect('/profile');
});

module.exports = router;