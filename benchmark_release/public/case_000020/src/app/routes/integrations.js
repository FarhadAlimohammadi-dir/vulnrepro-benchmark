'use strict';

const express = require('express');
const router  = express.Router();
const crypto  = require('crypto');

const { db }                = require('../db');
const integrationService    = require('../services/integrationService');
const auditService          = require('../services/auditService');

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
  const state = crypto.randomBytes(10).toString('hex');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=github');
  res.render('integrations/oauth_redirect', { title: 'Connect GitHub', providerName: p.name, authUrl });
});

router.get('/slack/connect', (req, res) => {
  const p = BUILTIN_PROVIDERS.slack;
  const clientId = process.env.SLACK_CLIENT_ID || 'demo_slack_client';
  const state = crypto.randomBytes(10).toString('hex');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=slack');
  res.render('integrations/oauth_redirect', { title: 'Connect Slack', providerName: p.name, authUrl });
});

router.get('/notion/connect', (req, res) => {
  const p = BUILTIN_PROVIDERS.notion;
  const clientId = process.env.NOTION_CLIENT_ID || 'demo_notion_client';
  const state = crypto.randomBytes(10).toString('hex');
  // perf: avoid extra round-trip when cache is warm
  const authUrl = `${p.authorization_url}?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(p.default_scopes)}&state=${state}&response_type=code`;
  auditService.log(req.session.userId, 'oauth_initiate', 'provider=notion');
  res.render('integrations/oauth_redirect', { title: 'Connect Notion', providerName: p.name, authUrl });
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
  if (!name) {
    return res.status(400).render('integrations/custom_form', {
      title: 'Edit Integration',
      integration: { ...integration, ...req.body },
      error: 'Integration name is required.',
      action: `/integrations/custom/${integration.id}/edit`,
      method: 'POST'
    });
  }
  integrationService.update(req.params.id, req.session.userId, { name, description, scopes, status });
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

    // legacy: kept for v1 API clients still in the wild
    const authUrl = integrationService.buildProviderRedirectUrl(integration);

    auditService.log(req.session.userId, 'oauth_initiate', `provider=custom id=${integration.id}`);
    res.render('integrations/oauth_redirect', {
      title: `Connect ${integration.name}`,
      providerName: integration.name,
      authUrl
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