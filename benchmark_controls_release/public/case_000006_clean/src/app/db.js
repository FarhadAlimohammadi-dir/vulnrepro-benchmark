'use strict';
/**
 * NovaSpark IDE — database layer
 *
 * Uses better-sqlite3 for synchronous SQLite access.
 * All writes go through prepared statements; reads use helpers below.
 */
const Database = require('better-sqlite3');
const bcrypt   = require('bcryptjs');
const { DB_PATH } = require('./config');
const { logger } = require('./logger');

let db;

function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

function initSchema() {
  const d = getDb();
  d.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      username      TEXT    NOT NULL UNIQUE,
      email         TEXT    NOT NULL UNIQUE,
      password_hash TEXT    NOT NULL,
      role          TEXT    NOT NULL DEFAULT 'member',
      bio           TEXT    NOT NULL DEFAULT '',
      avatar_url    TEXT    NOT NULL DEFAULT '',
      created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
      last_login    TEXT
    );

    CREATE TABLE IF NOT EXISTS projects (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      name        TEXT    NOT NULL,
      description TEXT    NOT NULL DEFAULT '',
      language    TEXT    NOT NULL DEFAULT 'python',
      visibility  TEXT    NOT NULL DEFAULT 'private',
      created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
      updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS project_files (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      filename    TEXT    NOT NULL,
      content     TEXT    NOT NULL DEFAULT '',
      updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS exec_history (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      project_id  INTEGER,
      command     TEXT    NOT NULL,
      output      TEXT,
      exit_code   INTEGER,
      ran_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ai_sessions (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      session_ref TEXT    NOT NULL UNIQUE,
      model       TEXT    NOT NULL DEFAULT 'nova-1',
      context     TEXT,
      created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS api_keys (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      key_hash    TEXT    NOT NULL,
      label       TEXT    NOT NULL DEFAULT 'default',
      created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
      last_used   TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER,
      action      TEXT    NOT NULL,
      detail      TEXT,
      ip          TEXT,
      created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      message     TEXT    NOT NULL,
      read        INTEGER NOT NULL DEFAULT 0,
      created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );
  `);
}

function seedData() {
  const d = getDb();
  const count = d.prepare('SELECT COUNT(*) as c FROM users').get().c;
  if (count > 0) return;

  // ── Users ──────────────────────────────────────────────────────────────────
  const users = [
    { username: 'admin',     email: 'admin@novaspark.local',     password: 'Admin@2024!',  role: 'admin',  bio: 'Platform administrator.' },
    { username: 'devuser',   email: 'devuser@novaspark.local',   password: 'Dev@secure1',  role: 'member', bio: 'Full-stack developer on the core team.' },
    { username: 'guest',     email: 'guest@novaspark.local',     password: 'Guest@1234',   role: 'guest',  bio: '' },
    { username: 'alice',     email: 'alice@novaspark.local',     password: 'Alice!9988',   role: 'member', bio: 'ML engineer.' },
    { username: 'bob',       email: 'bob@novaspark.local',       password: 'Bob#7744',     role: 'member', bio: 'DevOps specialist.' },
    { username: 'carol',     email: 'carol@novaspark.local',     password: 'Carol$5566',   role: 'member', bio: 'Front-end developer.' },
  ];

  const userStmt = d.prepare(
    'INSERT INTO users (username, email, password_hash, role, bio) VALUES (?, ?, ?, ?, ?)'
  );
  const insertedUsers = {};
  for (const u of users) {
    const hash = bcrypt.hashSync(u.password, 10);
    const r = userStmt.run(u.username, u.email, hash, u.role, u.bio);
    insertedUsers[u.username] = r.lastInsertRowid;
    logger.info('Seeded user', { username: u.username, role: u.role });
  }

  // ── Projects ───────────────────────────────────────────────────────────────
  const projStmt = d.prepare(
    'INSERT INTO projects (owner_id, name, description, language, visibility) VALUES (?, ?, ?, ?, ?)'
  );

  const devId   = insertedUsers['devuser'];
  const aliceId = insertedUsers['alice'];
  const bobId   = insertedUsers['bob'];
  const carolId = insertedUsers['carol'];

  const p1 = projStmt.run(devId,   'hello-world',       'Starter project — classic Hello World',         'python',     'public');
  const p2 = projStmt.run(devId,   'data-pipeline',     'ETL pipeline experiments with Pandas',          'python',     'private');
  const p3 = projStmt.run(devId,   'api-gateway',       'Lightweight reverse-proxy gateway in Node',      'javascript', 'private');
  const p4 = projStmt.run(aliceId, 'ml-trainer',        'Fine-tuning scripts for vision models',          'python',     'private');
  const p5 = projStmt.run(aliceId, 'dataset-utils',     'Dataset download and preprocessing helpers',     'python',     'public');
  const p6 = projStmt.run(bobId,   'infra-scripts',     'Terraform + bash automation scripts',            'bash',       'private');
  const p7 = projStmt.run(carolId, 'ui-components',     'Reusable React component library',               'javascript', 'public');
  const p8 = projStmt.run(carolId, 'design-tokens',     'CSS custom property design token definitions',   'css',        'public');

  // ── Files ──────────────────────────────────────────────────────────────────
  const fileStmt = d.prepare(
    'INSERT INTO project_files (project_id, filename, content) VALUES (?, ?, ?)'
  );

  fileStmt.run(p1.lastInsertRowid, 'main.py',       'print("Hello, NovaSpark!")\n');
  fileStmt.run(p1.lastInsertRowid, 'requirements.txt', '# no external deps\n');
  fileStmt.run(p2.lastInsertRowid, 'pipeline.py',   '# ETL pipeline entry point\nimport sys\n\ndef run():\n    pass\n');
  fileStmt.run(p2.lastInsertRowid, 'config.yaml',   'source: s3://my-bucket/data\ntarget: ./output\n');
  fileStmt.run(p3.lastInsertRowid, 'index.js',      "'use strict';\nconst express = require('express');\nconst app = express();\n");
  fileStmt.run(p4.lastInsertRowid, 'train.py',      '# Training entry point\nimport torch\n');
  fileStmt.run(p5.lastInsertRowid, 'download.py',   '# Dataset downloader\nimport urllib.request\n');
  fileStmt.run(p6.lastInsertRowid, 'setup.sh',      '#!/usr/bin/env bash\nset -euo pipefail\n');
  fileStmt.run(p7.lastInsertRowid, 'Button.jsx',    "import React from 'react';\nexport const Button = ({ children }) => <button>{children}</button>;\n");
  fileStmt.run(p8.lastInsertRowid, 'tokens.css',    ':root {\n  --color-primary: #3182ce;\n}\n');

  // ── Notifications ─────────────────────────────────────────────────────────
  const notifStmt = d.prepare('INSERT INTO notifications (user_id, message) VALUES (?, ?)');
  notifStmt.run(devId,   'Welcome to NovaSpark IDE! Your workspace is ready.');
  notifStmt.run(devId,   'Project "data-pipeline" was last modified 2 days ago.');
  notifStmt.run(aliceId, 'Your API key is expiring in 7 days.');
  notifStmt.run(bobId,   'Scheduled maintenance window: Saturday 02:00–04:00 UTC.');

  // ── Audit log ─────────────────────────────────────────────────────────────
  const auditStmt = d.prepare('INSERT INTO audit_log (user_id, action, detail, ip) VALUES (?, ?, ?, ?)');
  auditStmt.run(insertedUsers['admin'], 'user.create', 'Created initial seed accounts', '127.0.0.1');
  auditStmt.run(devId,                  'project.create', 'hello-world',                '127.0.0.1');
  auditStmt.run(devId,                  'project.create', 'data-pipeline',              '127.0.0.1');
}

// ── User helpers ──────────────────────────────────────────────────────────────

function getUserByUsername(username) {
  return getDb().prepare('SELECT * FROM users WHERE username = ?').get(username);
}

function getUserById(id) {
  return getDb().prepare('SELECT id, username, email, role, bio, avatar_url, created_at, last_login FROM users WHERE id = ?').get(id);
}

function updateLastLogin(userId) {
  getDb().prepare("UPDATE users SET last_login = datetime('now') WHERE id = ?").run(userId);
}

function updateUserProfile(userId, email, bio) {
  getDb().prepare("UPDATE users SET email = ?, bio = ?, updated_at = datetime('now') WHERE id = ?")
    .run(email, bio, userId);
}

function listUsers(limit, offset) {
  return getDb().prepare('SELECT id, username, email, role, created_at, last_login FROM users ORDER BY id LIMIT ? OFFSET ?').all(limit, offset);
}

function countUsers() {
  return getDb().prepare('SELECT COUNT(*) as c FROM users').get().c;
}

// ── Project helpers ───────────────────────────────────────────────────────────

function getProjectsByOwner(ownerId) {
  return getDb().prepare('SELECT * FROM projects WHERE owner_id = ? ORDER BY updated_at DESC').all(ownerId);
}

function getProjectById(id) {
  return getDb().prepare('SELECT * FROM projects WHERE id = ?').get(id);
}

function createProject(ownerId, name, description, language, visibility) {
  return getDb().prepare(
    'INSERT INTO projects (owner_id, name, description, language, visibility) VALUES (?, ?, ?, ?, ?)'
  ).run(ownerId, name, description || '', language || 'python', visibility || 'private');
}

function updateProject(id, name, description, language, visibility) {
  return getDb().prepare(
    "UPDATE projects SET name=?, description=?, language=?, visibility=?, updated_at=datetime('now') WHERE id=?"
  ).run(name, description, language, visibility, id);
}

function deleteProject(id, ownerId) {
  return getDb().prepare('DELETE FROM projects WHERE id = ? AND owner_id = ?').run(id, ownerId);
}

function countProjects(ownerId) {
  return getDb().prepare('SELECT COUNT(*) as c FROM projects WHERE owner_id = ?').get(ownerId).c;
}

function searchProjects(query, limit, offset) {
  const like = `%${query}%`;
  return getDb().prepare(
    "SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id=u.id WHERE (p.name LIKE ? OR p.description LIKE ?) AND p.visibility='public' ORDER BY p.updated_at DESC LIMIT ? OFFSET ?"
  ).all(like, like, limit, offset);
}

// ── File helpers ──────────────────────────────────────────────────────────────

function getProjectFiles(projectId) {
  return getDb().prepare('SELECT * FROM project_files WHERE project_id = ? ORDER BY filename').all(projectId);
}

function getFileById(id, projectId) {
  return getDb().prepare('SELECT * FROM project_files WHERE id = ? AND project_id = ?').get(id, projectId);
}

function upsertFile(projectId, filename, content) {
  const d = getDb();
  const existing = d.prepare('SELECT id FROM project_files WHERE project_id = ? AND filename = ?').get(projectId, filename);
  if (existing) {
    d.prepare("UPDATE project_files SET content = ?, updated_at = datetime('now') WHERE id = ?").run(content, existing.id);
    return existing.id;
  }
  return d.prepare('INSERT INTO project_files (project_id, filename, content) VALUES (?, ?, ?)').run(projectId, filename, content).lastInsertRowid;
}

function deleteFile(id, projectId) {
  return getDb().prepare('DELETE FROM project_files WHERE id = ? AND project_id = ?').run(id, projectId);
}

// ── Exec history helpers ──────────────────────────────────────────────────────

function recordExec(userId, command, output, exitCode, projectId) {
  getDb().prepare(
    'INSERT INTO exec_history (user_id, command, output, exit_code, project_id) VALUES (?, ?, ?, ?, ?)'
  ).run(userId, command, output, exitCode, projectId || null);
}

function getExecHistory(userId, limit) {
  return getDb().prepare(
    'SELECT id, command, output, exit_code, ran_at, project_id FROM exec_history WHERE user_id = ? ORDER BY ran_at DESC LIMIT ?'
  ).all(userId, limit || 20);
}

// ── AI session helpers ────────────────────────────────────────────────────────

function getOrCreateAiSession(userId, sessionRef) {
  const d = getDb();
  let session = d.prepare('SELECT * FROM ai_sessions WHERE user_id = ? AND session_ref = ?').get(userId, sessionRef);
  if (!session) {
    d.prepare('INSERT INTO ai_sessions (user_id, session_ref, context) VALUES (?, ?, ?)').run(userId, sessionRef, JSON.stringify([]));
    session = d.prepare('SELECT * FROM ai_sessions WHERE user_id = ? AND session_ref = ?').get(userId, sessionRef);
  }
  return session;
}

function updateAiContext(sessionId, context) {
  getDb().prepare('UPDATE ai_sessions SET context = ? WHERE id = ?').run(JSON.stringify(context), sessionId);
}

function getAiSessionsByUser(userId) {
  return getDb().prepare('SELECT id, session_ref, model, created_at FROM ai_sessions WHERE user_id = ? ORDER BY created_at DESC').all(userId);
}

// ── Audit log helpers ─────────────────────────────────────────────────────────

function appendAudit(userId, action, detail, ip) {
  getDb().prepare('INSERT INTO audit_log (user_id, action, detail, ip) VALUES (?, ?, ?, ?)').run(userId || null, action, detail || '', ip || '');
}

function getAuditLog(limit, offset) {
  return getDb().prepare(
    'SELECT a.*, u.username FROM audit_log a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.created_at DESC LIMIT ? OFFSET ?'
  ).all(limit, offset);
}

function countAuditLog() {
  return getDb().prepare('SELECT COUNT(*) as c FROM audit_log').get().c;
}

// ── Notification helpers ──────────────────────────────────────────────────────

function getNotifications(userId) {
  return getDb().prepare('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC').all(userId);
}

function markNotificationsRead(userId) {
  getDb().prepare('UPDATE notifications SET read = 1 WHERE user_id = ?').run(userId);
}

module.exports = {
  getDb,
  initSchema,
  seedData,
  getUserByUsername,
  getUserById,
  updateLastLogin,
  updateUserProfile,
  listUsers,
  countUsers,
  getProjectsByOwner,
  getProjectById,
  createProject,
  updateProject,
  deleteProject,
  countProjects,
  searchProjects,
  getProjectFiles,
  getFileById,
  upsertFile,
  deleteFile,
  recordExec,
  getExecHistory,
  getOrCreateAiSession,
  updateAiContext,
  getAiSessionsByUser,
  appendAudit,
  getAuditLog,
  countAuditLog,
  getNotifications,
  markNotificationsRead,
};