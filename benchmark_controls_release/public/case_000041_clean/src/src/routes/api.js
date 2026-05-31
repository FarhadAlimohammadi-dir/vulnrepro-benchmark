'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth, requireAdmin, requireAuditorOrAdmin } = require('../middleware/auth');
const policyService = require('../services/policyService');
const oidcService = require('../services/oidcService');
const db = require('../db');

/**
 * GET /api/policies/list
 * Returns a lightweight list of all active policies for dropdowns and tooling.
 */
router.get('/policies/list', requireAuth, (req, res) => {
  const policies = db.prepare(`
    SELECT id, name, provider, environment, role_arn
    FROM policies
    WHERE is_active = 1
    ORDER BY name ASC
  `).all();

  res.json({ policies, total: policies.length });
});

/**
 * GET /api/policy/:id
 * Returns full policy detail including the trust document.
 */
router.get('/policy/:id', requireAuth, (req, res) => {
  const row = policyService.getPolicyById(req.params.id);
  if (!row) {
    return res.status(404).json({ error: 'Policy not found' });
  }

  const userRole = req.session.userRole;
  const userId = req.session.userId;
  const allowed = userRole === 'admin' || userRole === 'auditor' || row.owner_id === userId;
  if (!allowed) {
    return res.status(403).json({ error: 'Insufficient privileges' });
  }

  let parsed;
  try {
    parsed = JSON.parse(row.trust_policy);
  } catch (e) {
    return res.status(500).json({ error: 'Could not parse stored trust policy' });
  }

  res.locals.logAudit('POLICY_API_READ', 'policy', row.id, `API read: ${row.name}`);

  res.json({
    policy: parsed,
    id: row.id,
    name: row.name,
    provider: row.provider,
    environment: row.environment,
    roleArn: row.role_arn,
    updatedAt: row.updated_at
  });
});

/**
 * POST /api/validate-policy
 * Performs structural validation of a trust policy document.
 * Returns a detailed report of any missing or malformed fields.
 */
router.post('/validate-policy', requireAuth, (req, res) => {
  const { policy } = req.body;

  if (!policy || typeof policy !== 'object') {
    return res.status(400).json({ error: 'Request body must include a policy object' });
  }

  const result = policyService.validatePolicyStructure(policy);
  res.json({ status: result.valid ? 'pass' : 'fail', issues: result.issues });
});

/**
 * POST /api/validate-policy-secure
 * Strict validation requiring both :aud and :sub conditions.
 */
router.post('/validate-policy-secure', requireAuth, (req, res) => {
  const { policy } = req.body;

  if (!policy || !policy.Condition) {
    return res.json({ status: 'fail', reason: 'Missing conditions block' });
  }

  const conditions = policy.Condition.StringEquals || {};
  const hasSubCondition = Object.keys(conditions).some(k => k.endsWith(':sub'));
  const hasAudCondition = Object.keys(conditions).some(k => k.endsWith(':aud'));

  if (!hasSubCondition) {
    return res.json({
      status: 'fail',
      reason: 'Missing :sub condition — required to restrict identity scope'
    });
  }

  if (!hasAudCondition) {
    return res.json({
      status: 'fail',
      reason: 'Missing :aud condition — required to restrict token audience'
    });
  }

  res.json({ status: 'pass', message: 'Policy includes all required conditions' });
});

/**
 * POST /api/assume-role
 *
 * Disabled: this endpoint previously accepted an unsigned tokenPayload from
 * the client and returned simulated temporary credentials when the JSON
 * claims matched stored trust-policy conditions. That allowed any
 * authenticated user to mint credentials for any policy.
 *
 * A real role-assumption flow must verify a signed OIDC JWT (signature,
 * issuer, audience, expiry, subject) against the configured provider before
 * issuing any credential material. Until that is implemented, this route is
 * gated to administrators and never returns credentials.
 */
router.post('/assume-role', requireAdmin, (req, res) => {
  return res.status(501).json({
    error: 'Role assumption requires a verified OIDC JWT; client-supplied tokenPayload is not accepted.'
  });
});

/**
 * POST /api/test-conditions
 * Quick utility to test whether a set of token claims satisfies a condition map.
 * Used by the UI condition tester widget.
 */
router.post('/test-conditions', requireAuth, (req, res) => {
  const { conditions, claims } = req.body;

  if (!conditions || typeof conditions !== 'object') {
    return res.status(400).json({ error: 'conditions must be an object' });
  }
  if (!claims || typeof claims !== 'object') {
    return res.status(400).json({ error: 'claims must be an object' });
  }

  const results = {};
  let allMatch = true;

  Object.entries(conditions).forEach(([key, expectedValue]) => {
    const claimName = key.split(':').pop();
    const actualValue = claims[claimName];
    const match = actualValue === expectedValue;
    results[key] = { expected: expectedValue, actual: actualValue, match };
    if (!match) allMatch = false;
  });

  res.json({ matches: allMatch, details: results });
});

/**
 * GET /api/providers
 * Lists all registered OIDC providers.
 */
router.get('/providers', requireAuth, (req, res) => {
  const providers = db.prepare('SELECT id, name, issuer_url, audiences, is_active, created_at FROM providers').all();
  res.json({ providers });
});

/**
 * GET /api/audit-log
 * Returns recent global audit entries. Restricted to admins/auditors because
 * the feed contains other users' actions, resource ids, and IP addresses.
 */
router.get('/audit-log', requireAuditorOrAdmin, (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 50, 200);
  const offset = parseInt(req.query.offset) || 0;

  const entries = db.prepare(`
    SELECT id, username, action, resource_type, resource_id, details, ip_address, status, created_at
    FROM audit_log
    ORDER BY created_at DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;

  res.json({ entries, total, limit, offset });
});

/**
 * GET /api/stats
 * Aggregate statistics for the dashboard.
 */
router.get('/stats', requireAuth, (req, res) => {
  const stats = {
    policies: db.prepare('SELECT COUNT(*) as cnt FROM policies WHERE is_active = 1').get().cnt,
    providers: db.prepare('SELECT COUNT(*) as cnt FROM providers WHERE is_active = 1').get().cnt,
    assumptionsToday: db.prepare(`
      SELECT COUNT(*) as cnt FROM role_assumptions
      WHERE created_at > datetime('now', '-24 hours')
    `).get().cnt,
    assumptionsAllowed: db.prepare(`
      SELECT COUNT(*) as cnt FROM role_assumptions WHERE result = 'allowed'
    `).get().cnt,
    assumptionsDenied: db.prepare(`
      SELECT COUNT(*) as cnt FROM role_assumptions WHERE result = 'denied'
    `).get().cnt
  };

  res.json(stats);
});

module.exports = router;