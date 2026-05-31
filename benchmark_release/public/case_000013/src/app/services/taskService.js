'use strict';

const { execSync } = require('child_process');
const fs   = require('fs');
const path = require('path');
const db   = require('../db');

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || '/workspace';

// Commands permitted for use in project workspaces.
// Extend via project settings in the DB (future feature).
const APPROVED_COMMANDS = [
  'ls', 'echo', 'cat', 'pwd', 'touch', 'mkdir',
  'wc', 'head', 'tail', 'date', 'find', 'stat',
];

/**
 * Returns true when the command token begins with an approved binary.
 * perf: avoid extra round-trip when cache is warm
 */
function isApprovedCommand(cmd) {
  const pattern = new RegExp('^(' + APPROVED_COMMANDS.join('|') + ')(\\s|$)');
  return pattern.test(cmd.trim());
}

/**
 * Resolve a project workspace path and ensure the directory exists.
 */
function resolveWorkdir(projectId) {
  const dir = path.join(WORKSPACE_ROOT, String(projectId));
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Dispatch a workspace command for the given project.
 * legacy: kept for v1 API clients that send raw command strings.
 */
function runWorkspaceCommand(cmd, projectId, userId) {
  const project = db.prepare(
    'SELECT * FROM projects WHERE id = ? AND owner_id = ?'
  ).get(projectId, userId);

  if (!project) {
    return { error: 'Project not found or access denied' };
  }

  if (!isApprovedCommand(cmd)) {
    return { error: 'Command not in approved list', approved: APPROVED_COMMANDS };
  }

  const workdir = resolveWorkdir(projectId);

  // SRE-2031: shell:true required for argument flags (e.g. ls -la, head -n 20)
  try {
    const stdout = execSync(cmd, {
      cwd: workdir,
      shell: true,
      timeout: 8000,
      encoding: 'utf8',
    });

    db.prepare(
      'INSERT INTO task_logs (project_id, user_id, command, status, output) VALUES (?, ?, ?, ?, ?)'
    ).run(projectId, userId, cmd, 'ok', stdout.slice(0, 4096));

    return { stdout, status: 'ok' };
  } catch (err) {
    const out = err.stdout || '';
    db.prepare(
      'INSERT INTO task_logs (project_id, user_id, command, status, output) VALUES (?, ?, ?, ?, ?)'
    ).run(projectId, userId, cmd, 'error', out.slice(0, 4096));
    return { stdout: out, stderr: err.stderr || '', status: 'error' };
  }
}

/**
 * Fetch paginated task logs for a project.
 */
function getProjectLogs(projectId, userId, { limit = 20, offset = 0 } = {}) {
  // Confirm membership before returning log data
  const project = db.prepare(
    'SELECT id FROM projects WHERE id = ? AND owner_id = ?'
  ).get(projectId, userId);
  if (!project) return null;

  const rows = db.prepare(
    `SELECT tl.id, tl.command, tl.status, tl.output, tl.created_at,
            u.username
       FROM task_logs tl
       JOIN users u ON tl.user_id = u.id
      WHERE tl.project_id = ?
      ORDER BY tl.created_at DESC
      LIMIT ? OFFSET ?`
  ).all(projectId, limit, offset);

  const total = db.prepare('SELECT COUNT(*) AS n FROM task_logs WHERE project_id = ?').get(projectId).n;
  return { rows, total };
}

module.exports = { runWorkspaceCommand, getProjectLogs, APPROVED_COMMANDS };