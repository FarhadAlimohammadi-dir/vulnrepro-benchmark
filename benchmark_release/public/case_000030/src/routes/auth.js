'use strict';

const express = require('express');
const router = express.Router();
const crypto = require('crypto');
const db = require('../models/database');
const { requireAuth } = require('../middleware/auth');
const { auditLog } = require('../services/audit');
const { verifyCodeChallenge } = require('../services/pkce');

// In-memory stores (shared via app.locals in server.js)
const authCodes = {};
const issuedTokens = {};

// Make tokens accessible to middleware
const initStores = (app) => {
  app.locals.issuedTokens = issuedTokens;
};

// GET /auth/login
router.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('auth/login', {
    title: 'Sign In — Nexus',
    user: null,
    error: req.query.reason === 'account_inactive' ? 'Your account has been deactivated.' : null,
    returnTo: req.session.returnTo || '/dashboard'
  });
});

// POST /auth/login
router.post('/login', (req, res) => {
  const { email, password, remember_me } = req.body;

  if (!email || !password) {
    return res.status(400).render('auth/login', {
      title: 'Sign In — Nexus',
      user: null,
      error: 'Email and password are required.',
      returnTo: '/dashboard'
    });
  }

  const user = db.getUser(email.toLowerCase().trim());

  if (!user || user.password !== password) {
    auditLog(null, 'login_failed', { email, ip: req.ip });
    return res.status(401).render('auth/login', {
      title: 'Sign In — Nexus',
      user: null,
      error: 'Invalid email or password.',
      returnTo: '/dashboard'
    });
  }

  req.session.userId = user.id;
  req.session.email = user.email;
  req.session.role = user.role;

  if (remember_me) {
    req.session.cookie.maxAge = 30 * 24 * 60 * 60 * 1000;
  }

  db.updateLastLogin(user.id);
  auditLog(user.id, 'login_success', { ip: req.ip });

  const returnTo = req.session.returnTo || '/dashboard';
  delete req.session.returnTo;
  res.redirect(returnTo);
});

// GET /auth/register
router.get('/register', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('auth/register', {
    title: 'Create Account — Nexus',
    user: null,
    error: null
  });
});

// POST /auth/register
router.post('/register', (req, res) => {
  const { email, password, display_name } = req.body;

  if (!email || !password || !display_name) {
    return res.status(400).render('auth/register', {
      title: 'Create Account — Nexus',
      user: null,
      error: 'All fields are required.'
    });
  }

  if (password.length < 8) {
    return res.status(400).render('auth/register', {
      title: 'Create Account — Nexus',
      user: null,
      error: 'Password must be at least 8 characters.'
    });
  }

  if (db.userExists(email.toLowerCase().trim())) {
    return res.status(409).render('auth/register', {
      title: 'Create Account — Nexus',
      user: null,
      error: 'An account with that email already exists.'
    });
  }

  const userId = crypto.randomUUID();
  db.addUser({
    id: userId,
    email: email.toLowerCase().trim(),
    password,
    display_name,
    role: 'user'
  });

  req.session.userId = userId;
  req.session.email = email.toLowerCase().trim();
  req.session.role = 'user';

  auditLog(userId, 'account_created', { ip: req.ip });
  res.redirect('/dashboard');
});

// GET /auth/forgot-password
router.get('/forgot-password', (req, res) => {
  res.render('auth/forgot', {
    title: 'Reset Password — Nexus',
    user: null,
    sent: false,
    error: null
  });
});

router.post('/forgot-password', (req, res) => {
  const { email } = req.body;
  // Always show success to prevent email enumeration
  res.render('auth/forgot', {
    title: 'Reset Password — Nexus',
    user: null,
    sent: true,
    error: null
  });
});

// GET /auth/logout
router.get('/logout', (req, res) => {
  const userId = req.session.userId;
  if (userId) {
    auditLog(userId, 'logout', { ip: req.ip });
  }
  req.session.destroy(() => res.redirect('/'));
});

// POST /auth/token — OAuth2 token endpoint (authorization_code grant with PKCE)
router.post('/token', (req, res) => {
  const { code, code_verifier, grant_type, client_id } = req.body;

  if (grant_type !== 'authorization_code') {
    return res.status(400).json({
      error: 'unsupported_grant_type',
      error_description: 'Only authorization_code grant is supported.'
    });
  }

  if (!code) {
    return res.status(400).json({ error: 'invalid_request', error_description: 'Missing code parameter.' });
  }

  const authData = authCodes[code];
  if (!authData) {
    return res.status(400).json({ error: 'invalid_grant', error_description: 'Authorization code not found or expired.' });
  }

  // Check code expiry (10 minutes)
  if (Date.now() - authData.issuedAt > 10 * 60 * 1000) {
    delete authCodes[code];
    return res.status(400).json({ error: 'invalid_grant', error_description: 'Authorization code has expired.' });
  }

  // PKCE verification
  const valid = verifyCodeChallenge(code_verifier, authData.codeChallenge, authData.challengeMethod || 'S256');
  if (!valid) {
    auditLog(authData.userId, 'token_exchange_failed', { reason: 'pkce_mismatch' });
    return res.status(400).json({ error: 'invalid_grant', error_description: 'Code verifier does not match.' });
  }

  const token = crypto.randomBytes(32).toString('hex');
  issuedTokens[token] = authData.userId;
  delete authCodes[code];

  auditLog(authData.userId, 'token_issued', { client_id: client_id || 'unknown' });

  res.json({
    access_token: token,
    token_type: 'Bearer',
    expires_in: 3600,
    scope: authData.scope || 'openid profile email'
  });
});

// GET /auth/profile — bearer-token-protected profile endpoint
router.get('/profile', (req, res) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'unauthorized', error_description: 'Missing bearer token.' });
  }

  const token = authHeader.slice(7);
  const userId = issuedTokens[token];
  if (!userId) {
    return res.status(401).json({ error: 'invalid_token', error_description: 'Token not recognized.' });
  }

  const user = db.getUserById(userId);
  if (!user) {
    return res.status(404).json({ error: 'not_found' });
  }

  res.json({
    sub: user.id,
    email: user.email,
    name: user.display_name,
    phone: user.phone,
    timezone: user.timezone,
    role: user.role
  });
});

// GET /auth/authorize — OAuth2 authorization endpoint
router.get('/authorize', (req, res) => {
  const { client_id, redirect_uri, response_type, scope, state, code_challenge, code_challenge_method } = req.query;

  const client = db.getOAuthClient(client_id);
  if (!client) {
    return res.status(400).render('error', {
      title: 'OAuth Error — Nexus',
      user: null,
      status: 400,
      message: 'Unknown client application.'
    });
  }

  if (!req.session.userId) {
    req.session.oauthParams = req.query;
    return res.redirect('/auth/login');
  }

  res.render('auth/consent', {
    title: `Authorize ${client.name} — Nexus`,
    user: db.getUserById(req.session.userId),
    client,
    scope: scope || 'openid profile email',
    state,
    redirect_uri,
    code_challenge,
    code_challenge_method: code_challenge_method || 'S256'
  });
});

router.post('/authorize', requireAuth, (req, res) => {
  const { client_id, redirect_uri, scope, state, code_challenge, code_challenge_method, action } = req.body;

  if (action === 'deny') {
    const url = new URL(redirect_uri);
    url.searchParams.set('error', 'access_denied');
    if (state) url.searchParams.set('state', state);
    return res.redirect(url.toString());
  }

  const code = crypto.randomBytes(20).toString('hex');
  authCodes[code] = {
    userId: req.session.userId,
    clientId: client_id,
    codeChallenge: code_challenge,
    challengeMethod: code_challenge_method || 'S256',
    redirectUri: redirect_uri,
    scope: scope || 'openid profile email',
    issuedAt: Date.now()
  };

  db.connectApp(req.session.userId, client_id, scope);
  auditLog(req.session.userId, 'oauth_authorized', { client_id, scope });

  const url = new URL(redirect_uri);
  url.searchParams.set('code', code);
  if (state) url.searchParams.set('state', state);
  res.redirect(url.toString());
});

// Expose authCodes for SSO routes
module.exports = router;
module.exports.authCodes = authCodes;
module.exports.issuedTokens = issuedTokens;
module.exports.initStores = initStores;