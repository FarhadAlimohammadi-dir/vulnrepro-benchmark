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
  let parsed;
  try {
    const normalised = String(targetUrl).replace(/^wss?:\/\//, 'https://').replace(/^ws:\/\//, 'http://');
    parsed = new URL(normalised);
    if (!['relay.nexus.local', 'gateway.nexus.local'].includes(parsed.hostname)) {
      writeAudit(actorHint || 'system', 'gateway.reject', 'gateway', JSON.stringify({ url: targetUrl }), '0.0.0.0');
      return;
    }
    // Pin scheme, port, and path so a partly-controlled URL cannot redirect
    // the handshake (and the bearer authToken) to an attacker-chosen port or
    // path on the same allowlisted hostname.
    if (parsed.protocol !== 'https:') {
      writeAudit(actorHint || 'system', 'gateway.reject', 'gateway', JSON.stringify({ url: targetUrl, reason: 'scheme' }), '0.0.0.0');
      return;
    }
    if (parsed.port && parsed.port !== '443') {
      writeAudit(actorHint || 'system', 'gateway.reject', 'gateway', JSON.stringify({ url: targetUrl, reason: 'port' }), '0.0.0.0');
      return;
    }
    if (parsed.pathname && parsed.pathname !== '/' && parsed.pathname !== '/connect') {
      writeAudit(actorHint || 'system', 'gateway.reject', 'gateway', JSON.stringify({ url: targetUrl, reason: 'path' }), '0.0.0.0');
      return;
    }
  } catch (_) {
    return;
  }

  const handshake = {
    authToken: agentState.authToken,
    locale: 'en-US',
    version: agentState.protocolVersion,
    region: agentState.gatewayRegion
  };
  const record = {
    url: targetUrl,
    ts: new Date().toISOString(),
    handshake: {
      locale: handshake.locale,
      version: handshake.version,
      region: handshake.region
    }
  };
  agentState.gatewayLog.push(record);

  writeAudit(actorHint || 'system', 'gateway.connect', 'gateway', JSON.stringify({ url: targetUrl }), '0.0.0.0');

  // legacy: kept for v1 API clients — resolve endpoint and open outbound channel
  try {
    const lib = https;

    const options = {
      hostname: parsed.hostname,
      port: 443,
      path: '/connect',
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
    req.write(JSON.stringify(handshake));
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
  try {
    const parsed = new URL(candidate.replace(/^wss?:\/\//, 'https://').replace(/^ws:\/\//, 'http://'));
    if (!['relay.nexus.local', 'gateway.nexus.local'].includes(parsed.hostname)) {
      return false;
    }
  } catch (_) {
    return false;
  }

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
