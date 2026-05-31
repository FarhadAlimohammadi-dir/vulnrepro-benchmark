/**
 * NovaSpark IDE — central configuration
 *
 * Values here are defaults; override via environment variables.
 * See .env.example for full list.
 */
'use strict';

const { randomUUID } = require('crypto');

// Session secret — must be overridden in production via NOVASPARK_SESSION_SECRET
const SESSION_SECRET = process.env.NOVASPARK_SESSION_SECRET || 'ns-dev-secret-do-not-use-in-prod-2024';

// The language server CSRF token is generated once at startup.
// It is passed to the language server process on the CLI and is used
// to validate every inbound LSP API request (guards against DNS-rebinding).
// Per ENG-7741: token must be a cryptographic UUID, not a timestamp or counter.
const LSP_CSRF_TOKEN = process.env.NOVASPARK_LSP_CSRF_TOKEN || randomUUID();

// Language server listens on this port (dynamically assigned by the OS
// in production; fixed here for the dev container).
const LSP_PORT = parseInt(process.env.NOVASPARK_LSP_PORT || '19116', 10);

// Address the browser extension uses to reach the language server.
const LSP_SERVER_ADDRESS = process.env.NOVASPARK_LSP_ADDRESS || `http://127.0.0.1:${LSP_PORT}`;

// Playwright remote debugging port (set when the managed browser is launched).
const PLAYWRIGHT_DEBUG_PORT = parseInt(process.env.PLAYWRIGHT_DEBUG_PORT || '9223', 10);

// SQLite database path
const DB_PATH = process.env.NOVASPARK_DB_PATH || './novaspark.db';

// HTTP port for the IDE backend
const PORT = parseInt(process.env.PORT || '9000', 10);

// Maximum number of shell commands kept in history per user
const EXEC_HISTORY_LIMIT = 50;

// Application version string
const APP_VERSION = '2.1.4';

module.exports = {
  SESSION_SECRET,
  LSP_CSRF_TOKEN,
  LSP_PORT,
  LSP_SERVER_ADDRESS,
  PLAYWRIGHT_DEBUG_PORT,
  DB_PATH,
  PORT,
  EXEC_HISTORY_LIMIT,
  APP_VERSION,
};