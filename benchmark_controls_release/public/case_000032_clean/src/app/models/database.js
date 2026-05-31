'use strict';

const Database = require('better-sqlite3');
const path = require('path');

let dbInstance = null;

function initDb() {
  if (dbInstance) return dbInstance;

  const dbPath = process.env.DB_PATH || ':memory:';
  dbInstance = new Database(dbPath);

  dbInstance.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      email TEXT,
      instagram_id TEXT,
      role TEXT DEFAULT 'user',
      created_at INTEGER NOT NULL,
      last_login INTEGER,
      bio TEXT,
      website TEXT,
      is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS apps (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      owner_id TEXT NOT NULL,
      redirect_uri TEXT,
      scopes TEXT,
      pixel_id TEXT,
      secret TEXT,
      created_at INTEGER NOT NULL,
      is_active INTEGER DEFAULT 1,
      description TEXT
    );

    CREATE TABLE IF NOT EXISTS oauth_codes (
      code TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      app_id TEXT NOT NULL,
      redirect_uri TEXT,
      scope TEXT,
      issued_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      nonce TEXT,
      used INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS sessions (
      sid TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      ip_address TEXT,
      user_agent TEXT
    );

    CREATE TABLE IF NOT EXISTS api_tokens (
      token TEXT PRIMARY KEY,
      app_id TEXT NOT NULL,
      owner_id TEXT NOT NULL,
      scope TEXT,
      created_at INTEGER NOT NULL,
      expires_at INTEGER,
      is_revoked INTEGER DEFAULT 0,
      last_used INTEGER
    );

    CREATE TABLE IF NOT EXISTS graph_requests (
      id TEXT PRIMARY KEY,
      token TEXT,
      url TEXT,
      referrer TEXT,
      pixel_id TEXT,
      ip_address TEXT,
      user_agent TEXT,
      timestamp INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pixel_events (
      id TEXT PRIMARY KEY,
      pixel_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      page_url TEXT,
      referrer TEXT,
      custom_data TEXT,
      session_id TEXT,
      timestamp INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id TEXT PRIMARY KEY,
      actor_id TEXT,
      action TEXT NOT NULL,
      resource_type TEXT,
      resource_id TEXT,
      details TEXT,
      ip_address TEXT,
      timestamp INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      type TEXT NOT NULL,
      message TEXT NOT NULL,
      is_read INTEGER DEFAULT 0,
      created_at INTEGER NOT NULL
    );
  `);

  console.log('[DB] Schema initialized');
  return dbInstance;
}

function getDb() {
  if (!dbInstance) {
    throw new Error('Database not initialized. Call initDb() first.');
  }
  return dbInstance;
}

module.exports = { initDb, getDb };