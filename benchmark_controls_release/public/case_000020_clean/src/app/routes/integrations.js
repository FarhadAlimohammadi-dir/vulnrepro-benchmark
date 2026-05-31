'use strict';

const express = require('express');
const router  = express.Router();
const crypto  = require('crypto');

const { db }                = require('../db');
const integrationService    = require('../services/integrationService');
const auditService          = require('../services/auditService');

function issueOAuthState(req, provider) {
  const state = crypto.randomBytes(16).toString('hex');
  req.session.oauthStates = req.session.oauthStates || {};
  req.session.oauthStates[state] = {
    provider,
    createdAt: Date.now()
  };
  return state;
}

function consumeOAuthState(req, state) {
  if (!state || !req.session.oauthStates || !req.session.oauthStates[state]) {
    return false;
  }
  const record = req.session.oauthStates[state];
  delete req.session.oauthStates[state];
  return Date.now() - record.createdAt <= 10 * 60 * 1000;
}

// ── Built-in provider stubs ────────────────────────────────────────────────────
const BUILTIN_PROVIDERS = {
  github: {
    name: 'GitHub',
    authorization_url: 'https://github.com/login/oauth/authorize',
    token_url: 'https://github.com/login/oauth/token',
    default_scopes: 'repo read:user'
  },
  slack: {
    name: 'Slack',
    authorization_url: 'https://slack.com/oauth/v2/authorize',
    token_url: 'https://slack.com/api/oauth.v2.access',
    default_scopes: 'channels:read chat:write'
  },
  notion: {
    name: 'Notion',
    authorization_url: 'https://api.notion.com/v1/oauth/authorize',
    token_url: 'https://api.notion.com/v1/oauth/token',
    default_scopes: 'read_content'
  }
};

// ── List integrations (paginated) ─────────────────────────────────────────────
router.get('/', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const { rows, total, totalPages } = integrationService.listByOwner(req.session.userId, { page, pageSize: 10 });
  res.render('integrations/index', {
    title: 'My Integrations',
    integrations: rows,
    total,
    page,
    totalPages,
    search: req.query.search || ''
  });
});

// ── Search integrations ────────────────────────────────────────────────────────
router.get('/search', (req, res) => {
  const q = (req.query.q || '').trim();
  if (!q) return res.redirect('/integrations');
  const rows = db.prepare(
    "SELECT * FROM integrations WHERE owner_id = ? AND (name LIKE ? OR description LIKE ?) ORDER BY created_at DESC"
  ).all(req.session.userId, `%${q}%`, `%${q}%`);
  res.render('integrations/index', {
    title: `Search: ${q}`,
    integrations: rows,
    total: rows.length,
    page: 1,
    totalPages: 1,
    search: q
  });
});

// ── Built-in provider connect pages ───────────────────────────────────────────
router.get('/github/connect', (req, res) => {
  const p = BUILTIN_PROVIDERS.github;
  const clientId = process.env.GITHUB_CLIENT_ID || 'demo_github_client';
  const state = issueOAuthState(req, 'github');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=github');
  res.render('integrations/oauth_redirect', { title: 'Connect GitHub', providerName: p.name, authUrl, isCustom: false });
});

router.get('/slack/connect', (req, res) => {
  const p = BUILTIN_PROVIDERS.slack;
  const clientId = process.env.SLACK_CLIENT_ID || 'demo_slack_client';
  const state = issueOAuthState(req, 'slack');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=slack');
  res.render('integrations/oauth_redirect', { title: 'Connect Slack', providerName: p.name, authUrl, isCustom: false });
});

router.get('/notion/connect', (req, res) => {
  const p = BUILTIN_PROVIDERS.notion;
  const clientId = process.env.NOTION_CLIENT_ID || 'demo_notion_client';
  const state = issueOAuthState(req, 'notion');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=notion');
  res.render('integrations/oauth_redirect', { title: 'Connect Notion', providerName: p.name, authUrl, isCustom: false });
});

// ── Webhook HMAC verification ─────────────────────────────────────────────────
// SRE-2031: batches up to 50 items per call from inbound webhook processors
router.post('/webhook/verify', (req, res) => {
  const { payload, signature } = req.body;
  if (!payload || !signature) {
    return res.status(400).json({ ok: false, reason: 'missing fields' });
  }
  const secret = process.env.WEBHOOK_SECRET || 'default-webhook-secret';
  let expected;
  try {
    expected = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  } catch (err) {
    return res.status(400).json({ ok: false, reason: 'invalid payload encoding' });
  }
  let match = false;
  try {
    match = crypto.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expected, 'hex'));
  } catch (_) {
    return res.json({ ok: false, reason: 'signature length mismatch' });
  }
  auditService.log(req.session.userId, 'webhook_verify', `match=${match}`);
  res.json({ ok: match });
});

// ── OAuth callback handler (receives code from provider) ─────────────────────
// Handles the return leg of the authorization_code grant flow.
router.get('/callback', (req, res) => {
  const { code, state, error } = req.query;
  if (error) {
    return res.render('integrations/callback', { title: 'Authorization Cancelled', success: false, message: `Provider returned: ${error}` });
  }
  if (!code) {
    return res.render('integrations/callback', { title: 'Authorization Error', success: false, message: 'No authorization code received.' });
  }
  const signed = integrationService.verifySignedState(state);
  const stateOk = signed
    ? signed.ownerId === req.session.userId &&
      !!integrationService.getByIdForOwner(signed.integrationId, req.session.userId)
    : consumeOAuthState(req, state);
  if (!stateOk) {
    auditService.log(req.session.userId, 'oauth_callback_rejected', 'invalid_state');
    return res.status(400).render('integrations/callback', {
      title: 'Authorization Error',
      success: false,
      message: 'Authorization state could not be verified.'
    });
  }
  // In a full deployment the code would be exchanged for an access token here.
  // For this demo instance the code is acknowledged and stored as a placeholder.
  auditService.log(req.session.userId, 'oauth_callback', `state=${state}`);
  res.render('integrations/callback', { title: 'Authorization Complete', success: true, message: 'Provider authorization completed successfully.' });
});

// ── New custom integration form ────────────────────────────────────────────────
router.get('/custom/new', (req, res) => {
  res.render('integrations/custom_form', {
    title: 'Add Custom Integration',
    integration: {},
    error: null,
    action: '/integrations/custom',
    method: 'POST'
  });
});

// ── Create custom integration ─────────────────────────────────────────────────
router.post('/custom', (req, res) => {
  const { name, authorization_url, token_url, client_id, description, scopes } = req.body;

  if (!name || !authorization_url || !token_url || !client_id) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Add Custom Integration',
      integration: req.body,
      error: 'Name, Authorization URL, Token URL, and Client ID are all required.',
      action: '/integrations/custom',
      method: 'POST'
    });
  }

  if (name.length > 120) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Add Custom Integration',
      integration: req.body,
      error: 'Integration name must be 120 characters or fewer.',
      action: '/integrations/custom',
      method: 'POST'
    });
  }
  try {
    const auth = new URL(authorization_url);
    const token = new URL(token_url);
    if (auth.protocol !== 'https:' || token.protocol !== 'https:') {
      throw new Error('invalid protocol');
    }
    if (!integrationService.isAllowedProviderHost(auth.hostname) ||
        !integrationService.isAllowedProviderHost(token.hostname)) {
      throw new Error('provider host not in allow-list');
    }
  } catch (_) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Add Custom Integration',
      integration: req.body,
      error: 'Authorization URL and Token URL must be HTTPS URLs whose host is on the approved provider list.',
      action: '/integrations/custom',
      method: 'POST'
    });
  }

  const newId = integrationService.create(req.session.userId, {
    name: name.trim(),
    description: (description || '').trim(),
    provider_type: 'custom',
    authorization_url: authorization_url.trim(),
    token_url: token_url.trim(),
    client_id: client_id.trim(),
    scopes: (scopes || '').trim()
  });

  auditService.log(req.session.userId, 'integration_created', `id=${newId} name=${name.trim()}`);
  res.redirect('/dashboard');
});

// ── Edit custom integration form ──────────────────────────────────────────────
router.get('/custom/:id/edit', (req, res) => {
  const integration = integrationService.getByIdForOwner(req.params.id, req.session.userId);
  if (!integration || integration.provider_type !== 'custom') {
    return res.status(404).render('error', { title: 'Not Found', message: 'Integration not found.', code: 404 });
  }
  res.render('integrations/custom_form', {
    title: 'Edit Integration',
    integration,
    error: null,
    action: `/integrations/custom/${integration.id}/edit`,
    method: 'POST'
  });
});

router.post('/custom/:id/edit', (req, res) => {
  const integration = integrationService.getByIdForOwner(req.params.id, req.session.userId);
  if (!integration || integration.provider_type !== 'custom') {
    return res.status(404).render('error', { title: 'Not Found', message: 'Integration not found.', code: 404 });
  }
  const { name, description, scopes, status } = req.body;
  const nextStatus = status || 'active';
  if (!name) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Edit Integration',
      integration: { ...integration, ...req.body },
      error: 'Integration name is required.',
      action: `/integrations/custom/${integration.id}/edit`,
      method: 'POST'
    });
  }
  if (!['active', 'inactive'].includes(nextStatus)) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Edit Integration',
      integration: { ...integration, ...req.body, status: integration.status },
      error: 'Status must be active or inactive.',
      action: `/integrations/custom/${integration.id}/edit`,
      method: 'POST'
    });
  }
  integrationService.update(req.params.id, req.session.userId, { name, description, scopes, status: nextStatus });
  auditService.log(req.session.userId, 'integration_updated', `id=${req.params.id}`);
  res.redirect('/integrations');
});

// ── Connect: initiate OAuth flow for a custom provider ────────────────────────
// Renders the redirect interstitial for any registered custom provider.
router.get('/custom/:id/connect', (req, res) => {
  try {
    const integration = db.prepare(
      'SELECT * FROM integrations WHERE id = ? AND owner_id = ? AND provider_type = ?'
    ).get(req.params.id, req.session.userId, 'custom');

    if (!integration) {
      return res.status(404).render('error', { title: 'Not Found', message: 'Integration not found.', code: 404 });
    }

    // Signed state binds the redirect to this owner + integration so a stale
    // link or cross-user click cannot trigger an unbound provider hand-off.
    const authUrl = integrationService.buildProviderRedirectUrl(integration, req.session.userId);

    auditService.log(req.session.userId, 'oauth_initiate', `provider=custom id=${integration.id}`);
    res.render('integrations/oauth_redirect', {
      title: `Connect ${integration.name}`,
      providerName: integration.name,
      authUrl,
      isCustom: true
    });
  } catch (err) {
    console.error('[integrations] connect error:', err.message);
    res.status(500).render('error', { title: 'Error', message: 'Could not initiate the authorization flow.', code: 500 });
  }
});

// ── Delete integration ─────────────────────────────────────────────────────────
router.post('/custom/:id/delete', (req, res) => {
  const info = integrationService.remove(req.params.id, req.session.userId);
  if (info.changes > 0) {
    auditService.log(req.session.userId, 'integration_deleted', `id=${req.params.id}`);
  }
  res.redirect('/integrations');
});

module.exports = router;
