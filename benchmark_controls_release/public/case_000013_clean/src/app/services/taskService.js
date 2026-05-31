'use strict';

const { execFileSync } = require('child_process');
const fs   = require('fs');
const path = require('path');
const db   = require('../db');

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || '/workspace';

// Commands permitted for use in project workspaces.
// Extend via project settings in the DB (future feature).
// Removed file-content / file-mutation primitives (cat, touch, mkdir) — these
// can leave the workspace once any path-resolution gap exists. The remaining
// commands do not take file operands, so workspace confinement reduces to the
// process cwd.
const APPROVED_COMMANDS = {
  ls: '/bin/ls',
  echo: '/bin/echo',
  pwd: '/bin/pwd',
  date: '/bin/date',
};

function resolveApprovedBinary(name) {
  const candidate = APPROVED_COMMANDS[name];
  if (!candidate) return null;
  try {
    const real = fs.realpathSync(candidate);
    if (!path.isAbsolute(real)) return null;
    const stat = fs.statSync(real);
    if (!stat.isFile()) return null;
    return real;
  } catch (err) {
    return null;
  }
}

function parseApprovedCommand(cmd) {
  const parts = cmd.trim().split(/\s+/).filter(Boolean);
  const name = parts[0] || '';
  const resolved = resolveApprovedBinary(name);
  if (!resolved) return null;
  if (parts.some(part => /[;&|`$<>\\\n\r]/.test(part))) {
    return null;
  }
  return { name, binary: resolved, args: parts.slice(1) };
}

/**
 * Resolve a project workspace path and ensure the directory exists.
 */
function resolveWorkdir(projectId) {
  const dir = path.join(WORKSPACE_ROOT, String(projectId));
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function hasUnsafePathArg(parsed, workdir) {
  if (parsed.name === 'echo' || parsed.name === 'pwd' || parsed.name === 'date') {
    return false;
  }
  return parsed.args.some((arg) => {
    if (!arg) return false;
    if (arg.startsWith('-')) return true;
    if (path.isAbsolute(arg)) return true;
    const resolved = path.resolve(workdir, arg);
    const rel = path.relative(workdir, resolved);
    if (rel === '' ) return false;
    if (rel.startsWith('..') || path.isAbsolute(rel)) return true;
    return false;
  });
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

  const parsed = parseApprovedCommand(cmd);
  if (!parsed) {
    return { error: 'Command not in approved list', approved: Object.keys(APPROVED_COMMANDS) };
  }

  const workdir = resolveWorkdir(projectId);
  if (hasUnsafePathArg(parsed, workdir)) {
    return { error: 'Command path arguments must stay inside the project workspace' };
  }

  try {
    const stdout = execFileSync(parsed.binary, parsed.args, {
      cwd: workdir,
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
