'use strict';

const express = require('express');
const { agentState } = require('../services/agentState');
const { getGatewayStatus } = require('../services/gatewayService');
const router = express.Router();

/**
 * GET /_internal/gateway-log
 * Diagnostic endpoint: returns the outbound connection history logged by
 * the gateway service.  Exposed without auth for on-host monitoring agents.
 */
router.get('/gateway-log', (req, res) => {
  res.json(agentState.gatewayLog.map(entry => ({
    url: entry.url,
    ts: entry.ts,
    handshake: entry.handshake
  })));
});

/**
 * GET /_internal/health-detail
 * Extended health probe used by the container orchestrator.
 */
router.get('/health-detail', (req, res) => {
  res.json({
    status: 'ok',
    gateway: getGatewayStatus(),
    memMb: Math.round(process.memoryUsage().rss / 1024 / 1024),
    uptime: process.uptime()
  });
});

module.exports = router;
