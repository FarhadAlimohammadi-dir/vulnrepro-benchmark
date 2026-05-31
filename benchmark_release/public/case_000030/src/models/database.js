'use strict';

const Database = require('better-sqlite3');
const path = require('path');
const crypto = require('crypto');
const fs = require('fs');

const DATA_DIR = path.join(__dirname, '..', 'data');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const dbPath = path.join(DATA_DIR, 'nexus.db');
const db = new Database(dbPath);

function initialize() {
  db.exec(`
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      display_name TEXT,
      phone TEXT,
      timezone TEXT DEFAULT 'UTC',
      role TEXT DEFAULT 'user',
      is_active INTEGER DEFAULT 1,
      mfa_enabled INTEGER DEFAULT 0,
      last_login DATETIME,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS oauth_clients (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      client_secret TEXT NOT NULL,
      redirect_uris TEXT NOT NULL,
      scopes TEXT DEFAULT 'openid profile email',
      owner_id TEXT,
      is_active INTEGER DEFAULT 1,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS connected_apps (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      granted_scopes TEXT,
      connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT,
      action TEXT NOT NULL,
      details TEXT,
      ip_address TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS api_keys (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      name TEXT NOT NULL,
      key_hash TEXT NOT NULL,
      last_used DATETIME,
      expires_at DATETIME,
      is_active INTEGER DEFAULT 1,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS organizations (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      slug TEXT UNIQUE NOT NULL,
      owner_id TEXT,
      plan TEXT DEFAULT 'free',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS org_members (
      org_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      role TEXT DEFAULT 'member',
      joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(org_id, user_id),
      FOREIGN KEY(org_id) REFERENCES organizations(id),
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);
}

// Users
function addUser(data) {
  const stmt = db.prepare(`
    INSERT INTO users (id, email, password, display_name, role)
    VALUES (?, ?, ?, ?, ?)
  `);
  stmt.run(data.id, data.email, data.password, data.display_name || null, data.role || 'user');
}

function getUser(email) {
  return db.prepare('SELECT * FROM users WHERE email = ? AND is_active = 1').get(email);
}

function getUserById(id) {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(id);
}

function getAllUsers(limit = 50, offset = 0) {
  return db.prepare('SELECT id, email, display_name, role, is_active, last_login, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?').all(limit, offset);
}

function getUserCount() {
  return db.prepare('SELECT COUNT(*) as count FROM users').get().count;
}

function updateUserProfile(userId, data) {
  db.prepare(`
    UPDATE users SET display_name = ?, phone = ?, timezone = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `).run(data.display_name, data.phone, data.timezone, userId);
}

function updatePassword(userId, newPassword) {
  db.prepare('UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(newPassword, userId);
}

function updateLastLogin(userId) {
  db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?').run(userId);
}

function deactivateUser(userId) {
  db.prepare('UPDATE users SET is_active = 0 WHERE id = ?').run(userId);
}

function searchUsers(query, limit = 20) {
  return db.prepare(`
    SELECT id, email, display_name, role, is_active, created_at
    FROM users
    WHERE email LIKE ? OR display_name LIKE ?
    ORDER BY created_at DESC
    LIMIT ?
  `).all(`%${query}%`, `%${query}%`, limit);
}

// OAuth Clients
function addOAuthClient(data) {
  db.prepare(`
    INSERT INTO oauth_clients (id, name, client_secret, redirect_uris, scopes, owner_id)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(data.id, data.name, data.client_secret, data.redirect_uris, data.scopes, data.owner_id);
}

function getOAuthClient(id) {
  return db.prepare('SELECT * FROM oauth_clients WHERE id = ? AND is_active = 1').get(id);
}

function getAllOAuthClients() {
  return db.prepare('SELECT * FROM oauth_clients ORDER BY created_at DESC').all();
}

// Connected Apps
function getConnectedApps(userId) {
  return db.prepare(`
    SELECT ca.*, oc.name as app_name, oc.scopes as available_scopes
    FROM connected_apps ca
    JOIN oauth_clients oc ON ca.client_id = oc.id
    WHERE ca.user_id = ?
    ORDER BY ca.connected_at DESC
  `).all(userId);
}

function connectApp(userId, clientId, scopes) {
  const id = crypto.randomUUID();
  db.prepare(`
    INSERT OR REPLACE INTO connected_apps (id, user_id, client_id, granted_scopes)
    VALUES (?, ?, ?, ?)
  `).run(id, userId, clientId, scopes);
}

function disconnectApp(userId, clientId) {
  db.prepare('DELETE FROM connected_apps WHERE user_id = ? AND client_id = ?').run(userId, clientId);
}

// Activity Log
function addActivity(userId, action, details, ip) {
  db.prepare(`
    INSERT INTO activity_log (user_id, action, details, ip_address)
    VALUES (?, ?, ?, ?)
  `).run(userId, action, details ? JSON.stringify(details) : null, ip || null);
}

function getRecentActivity(userId, limit = 10) {
  return db.prepare(`
    SELECT * FROM activity_log
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT ?
  `).all(userId, limit);
}

function getAllActivity(limit = 100, offset = 0) {
  return db.prepare(`
    SELECT al.*, u.email as user_email
    FROM activity_log al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset);
}

// API Keys
function createApiKey(userId, name, expiresAt) {
  const id = crypto.randomUUID();
  const rawKey = crypto.randomBytes(32).toString('hex');
  const keyHash = crypto.createHash('sha256').update(rawKey).digest('hex');
  db.prepare(`
    INSERT INTO api_keys (id, user_id, name, key_hash, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, userId, name, keyHash, expiresAt || null);
  return { id, key: rawKey };
}

function getApiKeys(userId) {
  return db.prepare('SELECT id, name, last_used, expires_at, is_active, created_at FROM api_keys WHERE user_id = ? ORDER BY created_at DESC').all(userId);
}

function revokeApiKey(id, userId) {
  db.prepare('UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?').run(id, userId);
}

// Organizations
function addOrganization(data) {
  db.prepare(`
    INSERT INTO organizations (id, name, slug, owner_id, plan)
    VALUES (?, ?, ?, ?, ?)
  `).run(data.id, data.name, data.slug, data.owner_id, data.plan || 'free');
}

function getOrganizations() {
  return db.prepare('SELECT * FROM organizations ORDER BY created_at DESC').all();
}

function userExists(email) {
  return !!db.prepare('SELECT id FROM users WHERE email = ?').get(email);
}

module.exports = {
  db,
  initialize,
  addUser,
  getUser,
  getUserById,
  getAllUsers,
  getUserCount,
  updateUserProfile,
  updatePassword,
  updateLastLogin,
  deactivateUser,
  searchUsers,
  userExists,
  addOAuthClient,
  getOAuthClient,
  getAllOAuthClients,
  getConnectedApps,
  connectApp,
  disconnectApp,
  addActivity,
  getRecentActivity,
  getAllActivity,
  createApiKey,
  getApiKeys,
  revokeApiKey,
  addOrganization,
  getOrganizations
};