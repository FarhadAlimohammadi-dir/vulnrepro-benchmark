'use strict';

const express = require('express');
const { execFileSync } = require('child_process');
const { requireToken } = require('../middleware/auth');
const { agentState } = require('../services/agentState');
const { getGatewayStatus } = require('../services/gatewayService');
const { getDb } = require('../models/db');
const { writeAudit } = require('../services/auditService');
const router = express.Router();

const DIAGNOSTIC_COMMANDS = Object.freeze({
  uptime: { file: 'uptime', args: [] },
  uname:  { file: 'uname',  args: ['-a'] },
  disk:   { file: 'df',     args: ['-h'] }
});

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
 * POST /api/agent/run
 * Executes a fixed, allowlisted diagnostic command via execFile (no shell).
 * Requires a valid relay token.
 */
router.post('/run', requireToken, (req, res) => {
  const name = typeof req.body.diagnostic === 'string' ? req.body.diagnostic : null;
  const spec = name && Object.prototype.hasOwnProperty.call(DIAGNOSTIC_COMMANDS, name)
    ? DIAGNOSTIC_COMMANDS[name]
    : null;
  if (!spec) {
    return res.status(400).json({
      error: 'diagnostic is required',
      allowed: Object.keys(DIAGNOSTIC_COMMANDS)
    });
  }

  let output = '';
  let exitCode = 0;
  try {
    output = execFileSync(spec.file, spec.args, { timeout: 5000, encoding: 'utf8' });
  } catch (e) {
    output = (e.stderr || e.message || '').toString();
    exitCode = e.status || 1;
  }

  const db = getDb();
  db.prepare(
    'INSERT INTO exec_log (command, output, actor, exit_code) VALUES (?,?,?,?)'
  ).run(name, output, 'api-token', exitCode);

  writeAudit('api-token', 'exec.diagnostic', 'exec_log', JSON.stringify({ diagnostic: name }), req.ip);

  res.json({ ok: true, diagnostic: name, output, exitCode });
});

/**
 * GET /api/gateway/status  (duplicate path kept for backwards compatibility)
 */
router.get('/gateway-status', requireToken, (req, res) => {
  res.json(getGatewayStatus());
});

module.exports = router;