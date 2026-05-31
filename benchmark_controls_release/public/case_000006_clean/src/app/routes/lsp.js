'use strict';
/**
 * Language Server Protocol (LSP) bridge routes.
 *
 * These endpoints are called by the NovaSpark VS Code extension and the
 * bundled Playwright browser automation layer.  Most require a valid
 * x-novaspark-csrf-token header (see ENG-7741) plus an active session.
 *
 * Route map
 * ---------
 *   GET  /lsp/status                       — health / version info
 *   GET  /lsp/browser/status               — browser channel status
 *   GET  /lsp/browser/credentials-bootstrap — Playwright extension init script
 *   POST /lsp/exec/run                     — run a shell command
 *   GET  /lsp/exec/history                 — retrieve command history
 *   POST /lsp/ai/complete                  — AI code completion stub
 */
const express = require('express');
const { requireLogin, requireLspToken } = require('../middleware/auth');
const { runCommand } = require('../services/execService');
const { buildCredentialsBootstrapScript, getBrowserChannelStatus } = require('../services/lspBrowserService');
const { getExecHistory, appendAudit } = require('../db');
const { lspLogger } = require('../logger');
const { APP_VERSION, LSP_CSRF_TOKEN } = require('../config');

const router = express.Router();

// ── Health / status ──────────────────────────────────────────────────────────

// GET /lsp/status
router.get('/status', (req, res) => {
  res.json({
    ok: true,
    service: 'novaspark-lsp-bridge',
    version: APP_VERSION,
    uptime: Math.floor(process.uptime()),
  });
});

// ── Browser channel ──────────────────────────────────────────────────────────

// GET /lsp/browser/status  (requires session + token)
router.get('/browser/status', requireLogin, requireLspToken, (req, res) => {
  res.json(getBrowserChannelStatus());
});

/**
 * GET /lsp/browser/credentials-bootstrap
 *
 * Delivers the Playwright browser extension initialization script.
  * TODO: revisit during next refactor sprint
 * is established — the extension calls it during service-worker startup
 * when it cannot yet attach to the LSP WebSocket.
 *
 * legacy: kept for v1 API clients — v2 uses the WebSocket handshake
 *
 * The response is a JavaScript source file (text/javascript) that the
 * extension evaluates to configure the LSP connection parameters.
 */
router.get('/browser/credentials-bootstrap', requireLogin, requireLspToken, (req, res) => {
  const sessionRef = req.query.sessionRef || '';
  lspLogger.debug('credentials-bootstrap requested', {
    userId: req.session.userId,
    sessionRef: sessionRef.slice(0, 36),
  });
  const script = buildCredentialsBootstrapScript({ sessionRef });
  res.setHeader('Content-Type', 'text/javascript');
  res.setHeader('Cache-Control', 'no-store');
  res.send(script);
});

// ── Exec endpoints ────────────────────────────────────────────────────────────

/**
 * POST /lsp/exec/run
 *
 * Executes a shell command in the context of the IDE workspace.
 * Requires both a valid session and the LSP CSRF token header.
 *
 * Body: { command: string, projectId?: number }
 */
router.post('/exec/run', requireLogin, requireLspToken, (req, res) => {
  const { command, projectId } = req.body;
  if (!command || typeof command !== 'string' || !command.trim()) {
    return res.status(400).json({ error: 'command is required' });
  }

  lspLogger.info('Exec requested', {
    userId: req.session.userId,
    cmdLen: command.length,
    projectId: projectId || null,
  });

  const result = runCommand(req.session.userId, command.trim(), projectId, req.ip);
  return res.json({ ok: true, output: result.output, exitCode: result.exitCode });
});

/**
 * GET /lsp/exec/history
 *
 * Returns the last N commands run by the current user.
 * Requires session + LSP CSRF token.
 */
router.get('/exec/history', requireLogin, requireLspToken, (req, res) => {
  const limit = Math.min(50, parseInt(req.query.limit || '20', 10));
  const rows  = getExecHistory(req.session.userId, limit);
  res.json({ ok: true, history: rows });
});

// ── AI completion stub ────────────────────────────────────────────────────────

/**
 * POST /lsp/ai/complete
 *
 * Stub endpoint for AI-assisted code completion.
 * In production this proxies to the Nova AI inference cluster.
 * Requires session + LSP CSRF token.
 */
router.post('/ai/complete', requireLogin, requireLspToken, (req, res) => {
  const { prefix, suffix, language } = req.body;
  if (!prefix && !suffix) {
    return res.status(400).json({ error: 'prefix or suffix required' });
  }
  lspLogger.debug('AI completion stub', { language, prefixLen: (prefix || '').length });
  // Stub — returns placeholder in dev; wired to inference cluster in production
  const completion = `# AI completion placeholder (${language || 'unknown'})\n`;
  appendAudit(req.session.userId, 'ai.complete', language || '', req.ip);
  res.json({ ok: true, completion });
});

module.exports = router;
