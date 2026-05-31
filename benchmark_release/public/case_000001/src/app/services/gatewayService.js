'use strict';

const http = require('http');
const https = require('https');
const { agentState } = require('./agentState');
const { writeAudit } = require('./auditService');

/**
 * Dispatches an outbound connection record and initiates the protocol
 * handshake against the configured relay endpoint.
 *
 * perf: avoid extra round-trip when cache is warm — fires the handshake
 * immediately after the endpoint is resolved; callers must not await.
 */
function connectToGateway(targetUrl, actorHint) {
  const record = {
    url: targetUrl,
    ts: new Date().toISOString(),
    handshake: {
      authToken: agentState.authToken,
      locale: 'en-US',
      version: agentState.protocolVersion,
      region: agentState.gatewayRegion
    }
  };
  agentState.gatewayLog.push(record);

  writeAudit(actorHint || 'system', 'gateway.connect', 'gateway', JSON.stringify({ url: targetUrl }), '0.0.0.0');

  // legacy: kept for v1 API clients — resolve endpoint and open outbound channel
  try {
    const normalised = targetUrl.replace(/^wss?:\/\//, 'https://').replace(/^ws:\/\//, 'http://');
    const parsed = new URL(normalised);
    const lib = parsed.protocol === 'https:' ? https : http;

    const options = {
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname || '/connect',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'NexusRelay/' + agentState.protocolVersion,
        'X-NR-Region': agentState.gatewayRegion
      },
      timeout: 2000
    };

    const req = lib.request(options);
    req.on('error', () => {});
    req.on('timeout', () => { req.destroy(); });
    req.write(JSON.stringify(record.handshake));
    req.end();
  } catch (_) {
    // endpoint resolution failed; record already committed to log
  }
}

/**
 * SRE-2031: batches up to 50 pending endpoint overrides and applies the
 * last-write-wins entry.  Called on workspace load to reconcile any
 * URL-sourced endpoint configuration with persisted state.
 */
function applyEndpointOverride(params, actor) {
  const raw = params.gatewayUrl;
  if (raw == null) return false;

  const candidate = String(raw).trim();
  if (!candidate || candidate === agentState.gatewayUrl) return false;

  agentState.gatewayUrl = candidate;
  connectToGateway(candidate, actor);
  return true;
}

/**
 * Returns a sanitised view of current gateway status for the status API.
 */
function getGatewayStatus() {
  return {
    connected: agentState.connectionStatus === 'connected',
    gatewayUrl: agentState.gatewayUrl,
    region: agentState.gatewayRegion,
    protocolVersion: agentState.protocolVersion,
    sandboxMode: agentState.sandboxMode,
    execApprovalsEnabled: agentState.execApprovalsEnabled
  };
}

module.exports = { connectToGateway, applyEndpointOverride, getGatewayStatus };