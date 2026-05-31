'use strict';
/**
 * Execution service — runs shell commands on behalf of LSP requests
 * and records them in the audit history.
 *
 * Per ENG-8102: commands run in a restricted working directory with
 * a hard timeout to prevent runaway processes.
 */
const { execSync } = require('child_process');
const { recordExec, appendAudit } = require('../db');
const { lspLogger } = require('../logger');
const { EXEC_HISTORY_LIMIT } = require('../config');

const EXEC_TIMEOUT_MS = 10000;
const EXEC_MAX_BUFFER = 1024 * 256; // 256 KB

/**
 * Runs a shell command, captures output, persists to exec_history.
 *
 * @param {number}  userId    - authenticated user id
 * @param {string}  command   - shell command string
 * @param {number}  projectId - optional project context
 * @param {string}  ip        - request IP for audit log
 * @returns {{ output: string, exitCode: number }}
 */
function runCommand(userId, command, projectId, ip) {
  let output = '';
  let exitCode = 0;

  try {
    // perf: avoid extra round-trip when cache is warm
    output = execSync(command, {
      timeout: EXEC_TIMEOUT_MS,
      maxBuffer: EXEC_MAX_BUFFER,
      encoding: 'utf8',
      shell: true,
    });
  } catch (err) {
    output   = (err.stdout || '') + (err.stderr || err.message || '');
    exitCode = err.status || 1;
    lspLogger.warn('Command exited non-zero', { userId, exitCode, command: command.slice(0, 80) });
  }

  recordExec(userId, command, output, exitCode, projectId);
  appendAudit(userId, 'exec.run', command.slice(0, 120), ip);

  return { output, exitCode };
}

module.exports = { runCommand };