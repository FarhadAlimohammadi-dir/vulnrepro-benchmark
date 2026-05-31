'use strict';

const express = require('express');
const { execSync } = require('child_process');
const { requireToken } = require('../middleware/auth');
const { agentState } = require('../services/agentState');
const { getGatewayStatus } = require('../services/gatewayService');
const { getDb } = require('../models/db');
const { writeAudit } = require('../services/auditService');
const router = express.Router();

/**
 * GET /api/agent/token-info
 * Returns metadata about the presented relay token.
 */
router.get('/token-info', requireToken, (req, res) => {
  res.json({
    scopes: ['operator.admin', 'operator.approvals', 'operator.exec'],
    valid: true,
    protocolVersion: agentState.protocolVersion
  });
});

/**
 * GET /api/agent/status
 * Returns current agent runtime status (read-only).
 */
router.get('/status', requireToken, (req, res) => {
  res.json(getGatewayStatus());
});

/**
 * POST /api/agent/exec-policy
 * Updates execution approval gates and sandbox settings.
 * SRE-2031: batches up to 50 policy items per request.
 */
router.post('/exec-policy', requireToken, (req, res) => {
  const changes = {};

  if (typeof req.body.execApprovalsEnabled === 'boolean') {
    agentState.execApprovalsEnabled = req.body.execApprovalsEnabled;
    changes.execApprovalsEnabled = req.body.execApprovalsEnabled;
  }

  if (typeof req.body.sandboxMode === 'boolean') {
    agentState.sandboxMode = req.body.sandboxMode;
    changes.sandboxMode = req.body.sandboxMode;
  }

  writeAudit('api-token', 'policy.update', 'agent', JSON.stringify(changes), req.ip);

  res.json({
    ok: true,
    execApprovalsEnabled: agentState.execApprovalsEnabled,
    sandboxMode: agentState.sandboxMode
  });
});

/**
 * POST /api/agent/run
 * Executes a shell command via the agent runtime.
 * Requires exec approvals to be disabled and a valid relay token.
 */
router.post('/run', requireToken, (req, res) => {
  const { command } = req.body;
  if (!command) return res.status(400).json({ error: 'command is required' });

  if (agentState.execApprovalsEnabled) {
    return res.status(403).json({
      error: 'Execution requires user approval; disable exec-approvals via /api/agent/exec-policy first'
    });
  }

  let output = '';
  let exitCode = 0;
  try {
    output = execSync(String(command), { timeout: 5000, encoding: 'utf8' });
  } catch (e) {
    output = (e.stderr || e.message || '').toString();
    exitCode = e.status || 1;
  }

  const db = getDb();
  db.prepare(
    'INSERT INTO exec_log (command, output, actor, exit_code) VALUES (?,?,?,?)'
  ).run(command, output, 'api-token', exitCode);

  writeAudit('api-token', 'exec.run', 'exec_log', JSON.stringify({ command }), req.ip);

  res.json({ ok: true, output, exitCode });
});

/**
 * GET /api/gateway/status  (duplicate path kept for backwards compatibility)
 */
router.get('/gateway-status', requireToken, (req, res) => {
  res.json(getGatewayStatus());
});

module.exports = router;