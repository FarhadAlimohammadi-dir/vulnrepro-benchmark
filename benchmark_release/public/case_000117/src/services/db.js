'use strict';

const Database = require('better-sqlite3');
const bcrypt   = require('bcryptjs');
const path     = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '..', 'noteflow.db');
let db;

function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

function initialize() {
  const conn = getDb();

  conn.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      username   TEXT    UNIQUE NOT NULL,
      email      TEXT    UNIQUE NOT NULL,
      password   TEXT    NOT NULL,
      role       TEXT    NOT NULL DEFAULT 'user',
      created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS notes (
      id               TEXT    PRIMARY KEY,
      owner_id         INTEGER NOT NULL,
      title            TEXT    NOT NULL,
      raw_content      TEXT    NOT NULL,
      sanitized_content TEXT   NOT NULL,
      visibility       TEXT    NOT NULL DEFAULT 'private',
      tags             TEXT    NOT NULL DEFAULT '',
      created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
      updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS note_shares (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      note_id    TEXT    NOT NULL,
      user_id    INTEGER NOT NULL,
      permission TEXT    NOT NULL DEFAULT 'read',
      FOREIGN KEY (note_id) REFERENCES notes(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id    INTEGER,
      action     TEXT    NOT NULL,
      target_id  TEXT,
      ip_addr    TEXT,
      created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
  `);

  console.log('[DB] Schema initialized');
}

// ── Users ──────────────────────────────────────────────────────────────────

function createUser(username, email, password, role = 'user') {
  const hash = bcrypt.hashSync(password, 10);
  const conn = getDb();
  return conn.prepare(`
    INSERT INTO users (username, email, password, role)
    VALUES (?, ?, ?, ?)
  `).run(username, email, hash, role);
}

function getUserByUsername(username) {
  return getDb().prepare('SELECT * FROM users WHERE username = ?').get(username);
}

function getUserById(id) {
  return getDb().prepare('SELECT * FROM users WHERE id = ?').get(id);
}

function verifyPassword(plain, hash) {
  return bcrypt.compareSync(plain, hash);
}

// ── Notes ──────────────────────────────────────────────────────────────────

function createNote(id, ownerId, title, rawContent, sanitizedContent, visibility, tags) {
  return getDb().prepare(`
    INSERT INTO notes (id, owner_id, title, raw_content, sanitized_content, visibility, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(id, ownerId, title, rawContent, sanitizedContent, visibility, tags);
}

function getNoteById(id) {
  return getDb().prepare('SELECT * FROM notes WHERE id = ?').get(id);
}

function getNotesByOwner(ownerId) {
  return getDb().prepare(`
    SELECT * FROM notes WHERE owner_id = ? ORDER BY updated_at DESC
  `).all(ownerId);
}

function getAllNotes() {
  return getDb().prepare(`
    SELECT n.*, u.username FROM notes n
    JOIN users u ON n.owner_id = u.id
    ORDER BY n.updated_at DESC
  `).all();
}

function getPublicNotes() {
  return getDb().prepare(`
    SELECT n.*, u.username FROM notes n
    JOIN users u ON n.owner_id = u.id
    WHERE n.visibility = 'public'
    ORDER BY n.updated_at DESC
  `).all();
}

function updateNote(id, title, rawContent, sanitizedContent, visibility, tags) {
  return getDb().prepare(`
    UPDATE notes
    SET title = ?, raw_content = ?, sanitized_content = ?, visibility = ?, tags = ?,
        updated_at = datetime('now')
    WHERE id = ?
  `).run(title, rawContent, sanitizedContent, visibility, tags, id);
}

function deleteNote(id) {
  return getDb().prepare('DELETE FROM notes WHERE id = ?').run(id);
}

function searchNotes(ownerId, query) {
  const q = `%${query}%`;
  return getDb().prepare(`
    SELECT * FROM notes
    WHERE owner_id = ? AND (title LIKE ? OR tags LIKE ?)
    ORDER BY updated_at DESC
  `).all(ownerId, q, q);
}

// ── Shares ─────────────────────────────────────────────────────────────────

function shareNote(noteId, userId, permission) {
  return getDb().prepare(`
    INSERT OR REPLACE INTO note_shares (note_id, user_id, permission)
    VALUES (?, ?, ?)
  `).run(noteId, userId, permission);
}

function getSharesForNote(noteId) {
  return getDb().prepare(`
    SELECT ns.*, u.username FROM note_shares ns
    JOIN users u ON ns.user_id = u.id
    WHERE ns.note_id = ?
  `).all(noteId);
}

// ── Activity ───────────────────────────────────────────────────────────────

function logActivity(userId, action, targetId, ipAddr) {
  return getDb().prepare(`
    INSERT INTO activity_log (user_id, action, target_id, ip_addr)
    VALUES (?, ?, ?, ?)
  `).run(userId || null, action, targetId || null, ipAddr || null);
}

function getRecentActivity(limit = 50) {
  return getDb().prepare(`
    SELECT al.*, u.username FROM activity_log al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC LIMIT ?
  `).all(limit);
}

module.exports = {
  initialize,
  createUser,
  getUserByUsername,
  getUserById,
  verifyPassword,
  createNote,
  getNoteById,
  getNotesByOwner,
  getAllNotes,
  getPublicNotes,
  updateNote,
  deleteNote,
  searchNotes,
  shareNote,
  getSharesForNote,
  logActivity,
  getRecentActivity,
};