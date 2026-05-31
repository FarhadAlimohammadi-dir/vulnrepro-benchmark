'use strict';

const Database = require('better-sqlite3');
const path = require('path');

const dbPath = process.env.DB_PATH || path.join(__dirname, 'data.db');
const db = new Database(dbPath);

// Ensure WAL mode for better concurrent read performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE NOT NULL,
    email      TEXT UNIQUE,
    password   TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'user',
    bio        TEXT,
    avatar_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
  );

  CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL REFERENCES posts(id),
    user_id    INTEGER NOT NULL REFERENCES users(id),
    body       TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    action     TEXT NOT NULL,
    target     TEXT,
    meta       TEXT,
    ip         TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS widget_configs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    widget_type TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// ── Users ────────────────────────────────────────────────────────────────────
const userStmts = {
  insert:          db.prepare('INSERT OR IGNORE INTO users (username, email, password, role, bio) VALUES (?, ?, ?, ?, ?)'),
  byUsername:      db.prepare('SELECT * FROM users WHERE username = ?'),
  byId:            db.prepare('SELECT * FROM users WHERE id = ?'),
  updateLastLogin: db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?'),
  updateProfile:   db.prepare('UPDATE users SET bio = ?, avatar_url = ? WHERE id = ?'),
  list:            db.prepare('SELECT id, username, email, role, created_at, last_login FROM users ORDER BY id'),
  count:           db.prepare('SELECT COUNT(*) AS n FROM users'),
};

// ── Posts ────────────────────────────────────────────────────────────────────
const postStmts = {
  insert:   db.prepare('INSERT INTO posts (user_id, title, body, status) VALUES (?, ?, ?, ?)'),
  byId:     db.prepare('SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id WHERE p.id = ?'),
  list:     db.prepare('SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id WHERE p.status = ? ORDER BY p.created_at DESC LIMIT ? OFFSET ?'),
  listAll:  db.prepare('SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id ORDER BY p.created_at DESC LIMIT ? OFFSET ?'),
  count:    db.prepare('SELECT COUNT(*) AS n FROM posts WHERE status = ?'),
  countAll: db.prepare('SELECT COUNT(*) AS n FROM posts'),
  update:   db.prepare('UPDATE posts SET title = ?, body = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?'),
  delete:   db.prepare('DELETE FROM posts WHERE id = ? AND user_id = ?'),
  search:   db.prepare("SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id WHERE p.title LIKE ? OR p.body LIKE ? ORDER BY p.created_at DESC LIMIT 20"),
};

// ── Comments ─────────────────────────────────────────────────────────────────
const commentStmts = {
  insert:   db.prepare('INSERT INTO comments (post_id, user_id, body) VALUES (?, ?, ?)'),
  byPost:   db.prepare('SELECT c.*, u.username FROM comments c JOIN users u ON u.id = c.user_id WHERE c.post_id = ? ORDER BY c.created_at ASC'),
  delete:   db.prepare('DELETE FROM comments WHERE id = ? AND user_id = ?'),
};

// ── Audit log ────────────────────────────────────────────────────────────────
const auditStmts = {
  insert: db.prepare('INSERT INTO audit_log (user_id, action, target, meta, ip) VALUES (?, ?, ?, ?, ?)'),
  list:   db.prepare('SELECT a.*, u.username FROM audit_log a LEFT JOIN users u ON u.id = a.user_id ORDER BY a.created_at DESC LIMIT ? OFFSET ?'),
  count:  db.prepare('SELECT COUNT(*) AS n FROM audit_log'),
};

// ── Widget configs ───────────────────────────────────────────────────────────
const widgetStmts = {
  insert:    db.prepare('INSERT INTO widget_configs (user_id, widget_type, config_json, enabled) VALUES (?, ?, ?, ?)'),
  byUser:    db.prepare('SELECT * FROM widget_configs WHERE user_id = ? ORDER BY id'),
  byId:      db.prepare('SELECT * FROM widget_configs WHERE id = ?'),
  update:    db.prepare('UPDATE widget_configs SET config_json = ?, enabled = ? WHERE id = ? AND user_id = ?'),
  delete:    db.prepare('DELETE FROM widget_configs WHERE id = ? AND user_id = ?'),
};

module.exports = {
  // Users
  addUser: (username, email, password, role = 'user', bio = '') =>
    userStmts.insert.run(username, email, password, role, bio),
  getUserByUsername: (username) => userStmts.byUsername.get(username),
  getUserById: (id) => userStmts.byId.get(id),
  updateLastLogin: (id) => userStmts.updateLastLogin.run(id),
  updateProfile: (id, bio, avatarUrl) => userStmts.updateProfile.run(bio, avatarUrl, id),
  listUsers: () => userStmts.list.all(),
  userCount: () => userStmts.count.get().n,

  // Posts
  createPost: (userId, title, body, status = 'published') =>
    postStmts.insert.run(userId, title, body, status),
  getPost: (id) => postStmts.byId.get(id),
  listPosts: (status = 'published', limit = 10, offset = 0) =>
    postStmts.list.all(status, limit, offset),
  listAllPosts: (limit = 20, offset = 0) =>
    postStmts.listAll.all(limit, offset),
  countPosts: (status = 'published') => postStmts.count.get(status).n,
  countAllPosts: () => postStmts.countAll.get().n,
  updatePost: (id, userId, title, body, status) =>
    postStmts.update.run(title, body, status, id, userId),
  deletePost: (id, userId) => postStmts.delete.run(id, userId),
  searchPosts: (q) => postStmts.search.all(`%${q}%`, `%${q}%`),

  // Comments
  addComment: (postId, userId, body) => commentStmts.insert.run(postId, userId, body),
  getComments: (postId) => commentStmts.byPost.all(postId),
  deleteComment: (id, userId) => commentStmts.delete.run(id, userId),

  // Audit
  audit: (userId, action, target, meta, ip) =>
    auditStmts.insert.run(userId || null, action, target || null, meta ? JSON.stringify(meta) : null, ip || null),
  listAudit: (limit = 50, offset = 0) => auditStmts.list.all(limit, offset),
  countAudit: () => auditStmts.count.get().n,

  // Widgets
  createWidget: (userId, type, config, enabled = 1) =>
    widgetStmts.insert.run(userId, type, JSON.stringify(config), enabled),
  getWidgetsByUser: (userId) => widgetStmts.byUser.all(userId),
  getWidget: (id) => widgetStmts.byId.get(id),
  updateWidget: (id, userId, config, enabled) =>
    widgetStmts.update.run(JSON.stringify(config), enabled, id, userId),
  deleteWidget: (id, userId) => widgetStmts.delete.run(id, userId),
};