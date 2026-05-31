'use strict';

const Database = require('better-sqlite3');
const path = require('path');
const logger = require('../services/logger');

let db;

function initDb() {
  if (db) return db;

  const dbPath = process.env.DB_PATH || path.join(__dirname, '../../data/codeflow.db');

  // Ensure data directory exists
  const fs = require('fs');
  const dir = path.dirname(dbPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  createSchema(db);
  logger.info('Database initialized');
  return db;
}

function createSchema(db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      full_name TEXT,
      role TEXT DEFAULT 'user',
      bio TEXT,
      avatar_url TEXT,
      created_at INTEGER DEFAULT (strftime('%s', 'now')),
      last_login INTEGER,
      is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS oauth_clients (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      secret TEXT NOT NULL,
      description TEXT,
      owner_id TEXT,
      redirect_uris TEXT NOT NULL,
      scopes TEXT DEFAULT 'read',
      logo_url TEXT,
      website TEXT,
      created_at INTEGER DEFAULT (strftime('%s', 'now')),
      is_active INTEGER DEFAULT 1,
      FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS oauth_codes (
      code TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      redirect_uri TEXT NOT NULL,
      scope TEXT,
      state TEXT,
      expires_at INTEGER NOT NULL,
      created_at INTEGER DEFAULT (strftime('%s', 'now')),
      FOREIGN KEY (client_id) REFERENCES oauth_clients(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS access_tokens (
      token TEXT PRIMARY KEY,
      client_id TEXT,
      user_id TEXT NOT NULL,
      scope TEXT,
      issued_at INTEGER DEFAULT (strftime('%s', 'now')),
      expires_at INTEGER,
      is_revoked INTEGER DEFAULT 0,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS refresh_tokens (
      token TEXT PRIMARY KEY,
      access_token TEXT NOT NULL,
      user_id TEXT NOT NULL,
      client_id TEXT,
      issued_at INTEGER DEFAULT (strftime('%s', 'now')),
      expires_at INTEGER,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT,
      action TEXT NOT NULL,
      resource_type TEXT,
      resource_id TEXT,
      details TEXT,
      ip_address TEXT,
      user_agent TEXT,
      created_at INTEGER DEFAULT (strftime('%s', 'now'))
    );

    CREATE TABLE IF NOT EXISTS user_consents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      scopes TEXT,
      granted_at INTEGER DEFAULT (strftime('%s', 'now')),
      UNIQUE(user_id, client_id),
      FOREIGN KEY (user_id) REFERENCES users(id),
      FOREIGN KEY (client_id) REFERENCES oauth_clients(id)
    );

    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
    CREATE INDEX IF NOT EXISTS idx_tokens_user ON access_tokens(user_id);
    CREATE INDEX IF NOT EXISTS idx_codes_client ON oauth_codes(client_id);
  `);
}

function getDb() {
  if (!db) throw new Error('Database not initialized');
  return db;
}

module.exports = { initDb, getDb };