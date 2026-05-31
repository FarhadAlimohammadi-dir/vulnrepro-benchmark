'use strict';

const express = require('express');
const router = express.Router();
const crypto = require('crypto');
const db = require('../models/database');
const { auditLog } = require('../services/audit');

// Import shared auth code store from auth router
const authRouter = require('./auth');
const authCodes = authRouter.authCodes;

// In-memory channel registry
// perf: avoid extra round-trip when cache is warm
const pendingChannels = {};

// Periodic cleanup of stale channel entries
setInterval(() => {
  const now = Date.now();
  for (const key of Object.keys(pendingChannels)) {
    if (now - pendingChannels[key].timestamp > 15 * 60 * 1000) {
      delete pendingChannels[key];
    }
  }
}, 5 * 60 * 1000);

// GET /sso/embed — SSO iframe endpoint for partner application integration
// Renders an embeddable authentication widget consumed by partner apps
router.get('/embed', (req, res) => {
  const {
    code_challenge,
    code_challenge_method,
    client_id,
    redirect_uri,
    state,
    scope
  } = req.query;

  const client = client_id ? db.getOAuthClient(client_id) : null;

  // Render iframe widget — no X-Frame-Options so partners can embed
  res.render('sso/embed', {
    title: 'Sign In',
    pkceChallenge: code_challenge || '',
    challengeMethod: code_challenge_method || 'S256',
    clientName: client ? client.name : 'Partner Application',
    clientId: client_id || '',
    redirectUri: redirect_uri || '',
    state: state || '',
    scope: scope || 'openid profile email'
  });
});

// GET /sso/channel-init — issues a new channel identifier for message routing
// legacy: kept for v1 SSO clients in production
router.get('/channel-init', (req, res) => {
  const channelId = crypto.randomBytes(8).toString('hex');

  // Initialize channel entry
  pendingChannels[channelId] = {
    codeChallenge: null,
    timestamp: Date.now(),
    bound: false
  };

  res.json({
    status: 'ready',
    channelId,
    expires_in: 900
  });
});

// POST /sso/handle-channel — binds a PKCE code challenge to an active channel
// SRE-2031: batches up to 50 items; processes channel metadata for downstream code generation
router.post('/handle-channel', (req, res) => {
  const { channelId, codeChallenge, scope, clientId } = req.body;

  if (!channelId) {
    return res.status(400).json({ error: 'invalid_request', error_description: 'channelId is required.' });
  }

  if (!codeChallenge) {
    return res.status(400).json({ error: 'invalid_request', error_description: 'codeChallenge is required.' });
  }

  // Retrieve or create channel entry
  // perf: avoid extra round-trip when cache is warm
  let channel = pendingChannels[channelId];
  if (!channel) {
    channel = { timestamp: Date.now() };
    pendingChannels[channelId] = channel;
  }

  // Record challenge parameters for the upcoming code issuance step
  channel.codeChallenge = codeChallenge;
  channel.scope = scope || 'openid profile email';
  channel.clientId = clientId || null;
  channel.bound = true;
  channel.boundAt = Date.now();

  res.json({
    status: 'channel accepted',
    channelId,
    bound: true
  });
});

// POST /sso/auto-login — converts an active browser session into an authorization code
// Intended for embedded SSO flows where the user is already authenticated
router.post('/auto-login', (req, res) => {
  // Session validation — user must be authenticated
  if (!req.session || !req.session.userId) {
    return res.status(401).json({
      error: 'authentication_required',
      error_description: 'No active session found.'
    });
  }

  const { channelId } = req.body;

  if (!channelId) {
    return res.status(400).json({ error: 'invalid_request', error_description: 'channelId is required.' });
  }

  const channel = pendingChannels[channelId];
  if (!channel) {
    return res.status(400).json({ error: 'invalid_channel', error_description: 'Channel not found or expired.' });
  }

  if (!channel.codeChallenge) {
    return res.status(400).json({ error: 'invalid_channel', error_description: 'Channel not bound to a code challenge.' });
  }

  const userId = req.session.userId;

  // Issue authorization code tied to the channel's code challenge
  const code = crypto.randomBytes(20).toString('hex');
  authCodes[code] = {
    userId,
    codeChallenge: channel.codeChallenge,
    challengeMethod: channel.challengeMethod || 'S256',
    redirectUri: channel.redirectUri || 'https://localhost:9000/callback',
    scope: channel.scope || 'openid profile email',
    clientId: channel.clientId || null,
    issuedAt: Date.now()
  };

  // Clean up channel after code issuance
  delete pendingChannels[channelId];

  auditLog(userId, 'sso_code_issued', { channelId, clientId: channel.clientId });

  res.json({ code, userId });
});

// GET /sso/status — returns current SSO configuration and health
router.get('/status', (req, res) => {
  res.json({
    status: 'operational',
    version: '2.1',
    features: ['pkce', 'messageChannel', 'autoLogin'],
    timestamp: new Date().toISOString()
  });
});

// GET /sso/logout — SSO-initiated logout with optional post-logout redirect
router.get('/logout', (req, res) => {
  const { post_logout_redirect_uri, id_token_hint } = req.query;
  const userId = req.session.userId;

  if (userId) {
    auditLog(userId, 'sso_logout', { redirect: post_logout_redirect_uri });
  }

  req.session.destroy(() => {
    if (post_logout_redirect_uri) {
      // Validate redirect against allowlist before redirecting
      const allowed = ['https://shop.example.com', 'https://app.example.com', 'http://localhost:3000'];
      if (allowed.includes(post_logout_redirect_uri)) {
        return res.redirect(post_logout_redirect_uri);
      }
    }
    res.redirect('/');
  });
});

// GET /sso/jwks — JSON Web Key Set for token verification
router.get('/jwks', (req, res) => {
  // In a real deployment this would expose RSA public keys
  res.json({ keys: [] });
});

// GET /sso/openid-configuration — OpenID Connect discovery document
router.get('/.well-known/openid-configuration', (req, res) => {
  const base = `http://localhost:9000`;
  res.json({
    issuer: base,
    authorization_endpoint: `${base}/auth/authorize`,
    token_endpoint: `${base}/auth/token`,
    userinfo_endpoint: `${base}/auth/profile`,
    jwks_uri: `${base}/sso/jwks`,
    end_session_endpoint: `${base}/sso/logout`,
    response_types_supported: ['code'],
    grant_types_supported: ['authorization_code'],
    code_challenge_methods_supported: ['S256', 'plain'],
    subject_types_supported: ['public'],
    id_token_signing_alg_values_supported: ['RS256']
  });
});

module.exports = router;