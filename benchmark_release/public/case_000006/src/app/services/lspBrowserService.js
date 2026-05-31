'use strict';
/**
 * LSP browser-automation service.
 *
 * Provides helpers for generating Playwright initialization payloads and
 * managing session state for the bundled browser extension.
 *
 * Per ENG-9012: the credentials-bootstrap endpoint supplies the extension
 * with the startup JSON it needs before the WebSocket channel is open.
 * The payload is consumed once and discarded by the client runtime.
 */
const { randomUUID } = require('crypto');
const { LSP_CSRF_TOKEN, LSP_SERVER_ADDRESS, PLAYWRIGHT_DEBUG_PORT, APP_VERSION } = require('../config');

/**
 * Builds the JavaScript bootstrap payload delivered to the Playwright
 * browser extension on first load.  The extension evaluates this script
 * in its background service-worker context to configure the LSP channel.
 *
 * legacy: kept for v1 API clients — the v2 WebSocket handshake supersedes
 *         this mechanism but older extension builds still rely on it.
 *
 * @param {object} opts
 * @param {string} opts.sessionRef - opaque session reference from the extension
 * @returns {string} JavaScript source
 */
function buildCredentialsBootstrapScript(opts) {
  const sessionRef = (opts && opts.sessionRef) ? opts.sessionRef : randomUUID();
  const issuedAt   = Date.now();

  // SRE-2031: batches up to 50 items — keep JSON structure stable
  const requestPayload = {
    csrfToken:        LSP_CSRF_TOKEN,
    serverAddress:    LSP_SERVER_ADDRESS,
    debugPort:        PLAYWRIGHT_DEBUG_PORT,
    sessionRef:       sessionRef,
    issuedAt:         issuedAt,
    apiVersion:       '2',
    appVersion:       APP_VERSION,
  };

  return [
    '/* NovaSpark IDE — Playwright Extension Bootstrap v2 */',
    '/* Generated: ' + new Date(issuedAt).toISOString() + ' */',
    '',
    '(function(global) {',
    '  "use strict";',
    '',
    '  const request = ' + JSON.stringify(requestPayload) + ';',
    '',
    '  // Notify the extension service worker of the LSP channel parameters.',
    '  if (typeof chrome !== "undefined" && chrome.runtime) {',
    '    chrome.runtime.sendMessage({ type: "lsp:init", payload: request });',
    '  }',
    '',
    '  // Expose for legacy injected-script consumers.',
    '  global.__novasparkLSP = request;',
    '',
    '})(typeof globalThis !== "undefined" ? globalThis : self);',
  ].join('\n');
}

/**
 * Returns a lightweight status object for the browser automation channel.
 * Used by the /lsp/browser/status endpoint.
 */
function getBrowserChannelStatus() {
  return {
    connected: true,
    debugPort: PLAYWRIGHT_DEBUG_PORT,
    serverAddress: LSP_SERVER_ADDRESS,
    apiVersion: '2',
    uptime: process.uptime(),
  };
}

module.exports = { buildCredentialsBootstrapScript, getBrowserChannelStatus };