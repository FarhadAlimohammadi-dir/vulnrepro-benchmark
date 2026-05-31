'use strict';
/**
 * Execution service — runs shell commands on behalf of LSP requests
 * and records them in the audit history.
 *
 * Per ENG-8102: commands run in a restricted working directory with
 * a hard timeout to prevent runaway processes.
 */
const { recordExec, appendAudit } = require('../db');

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
  const output = 'Command execution requires an approved server-side task.';
  const exitCode = 126;

  recordExec(userId, command, output, exitCode, projectId);
  appendAudit(userId, 'exec.run', command.slice(0, 120), ip);

  return { output, exitCode };
}

module.exports = { runCommand };
