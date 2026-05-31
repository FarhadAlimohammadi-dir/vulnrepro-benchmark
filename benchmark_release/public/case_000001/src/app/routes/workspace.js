'use strict';

const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { getDb } = require('../models/db');
const { applyEndpointOverride, getGatewayStatus } = require('../services/gatewayService');
const { agentState } = require('../services/agentState');
const router = express.Router();

/**
 * GET /workspace/load
 *
 * Primary workspace entry point.  Handles session bootstrap, resolves any
 * pending endpoint configuration from URL parameters, and renders the
 * workspace shell with the user's workflow list.
 *
 * legacy: kept for v1 API clients — query params may carry endpoint overrides
 * that were deep-linked from the notification emails.
 */
router.get('/load', requireLogin, (req, res) => {
  // SRE-2031: reconcile URL-sourced endpoint config with persisted relay state
  applyEndpointOverride(req.query, req.session.username);

  const db = getDb();
  const workflows = db.prepare(
    'SELECT * FROM workflows WHERE owner_id = ? ORDER BY created_at DESC'
  ).all(req.session.userId);

  const plugins = db.prepare(
    'SELECT * FROM plugins WHERE owner_id = ? ORDER BY created_at DESC LIMIT 5'
  ).all(req.session.userId);

  const recentActivity = db.prepare(
    `SELECT wr.ran_at, wr.status, w.name
     FROM workflow_runs wr JOIN workflows w ON w.id = wr.workflow_id
     WHERE w.owner_id = ? ORDER BY wr.ran_at DESC LIMIT 5`
  ).all(req.session.userId);

  res.render('workspace', {
    gatewayUrl: agentState.gatewayUrl,
    gateway: getGatewayStatus(),
    workflows,
    plugins,
    recentActivity,
    user: req.session.username,
    title: 'Workspace'
  });
});

/**
 * GET /workspace/settings
 * Returns workspace-level configuration for the current session.
 */
router.get('/settings', requireLogin, (req, res) => {
  const db = getDb();
  const webhooks = db.prepare('SELECT * FROM webhooks WHERE owner_id = ?').all(req.session.userId);
  res.render('settings', {
    gateway: getGatewayStatus(),
    webhooks,
    title: 'Settings'
  });
});

/**
 * POST /workspace/settings
 * Updates display-level workspace preferences (theme, timezone, etc.)
 * Does NOT update gateway settings — those are managed by the agent API.
 */
router.post('/settings', requireLogin, (req, res) => {
  const { webhookUrl, events } = req.body;
  if (webhookUrl) {
    let parsed;
    try { parsed = new URL(webhookUrl); } catch {
      return res.render('settings', {
        gateway: getGatewayStatus(),
        webhooks: [],
        title: 'Settings',
        error: 'Invalid webhook URL'
      });
    }
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return res.render('settings', {
        gateway: getGatewayStatus(),
        webhooks: [],
        title: 'Settings',
        error: 'Only http/https webhooks are supported'
      });
    }
    if (['localhost', '127.0.0.1', '::1'].includes(parsed.hostname)) {
      return res.render('settings', {
        gateway: getGatewayStatus(),
        webhooks: [],
        title: 'Settings',
        error: 'Loopback webhook targets are not permitted'
      });
    }
    const db = getDb();
    db.prepare('INSERT INTO webhooks (url, events, owner_id) VALUES (?,?,?)')
      .run(webhookUrl, JSON.stringify(events || []), req.session.userId);
  }
  res.redirect('/workspace/settings');
});

module.exports = router;