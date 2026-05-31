const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'app.db'));

// NOTE: WAL mode improves read concurrency for the marketplace catalogue
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    is_pro INTEGER DEFAULT 0,
    display_name TEXT,
    email TEXT
  );

  CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
  );

  CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category_id INTEGER
  );

  CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    filename TEXT,
    file_id TEXT UNIQUE,
    is_public INTEGER DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    detail TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
  );

  CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    notifications INTEGER DEFAULT 1,
    theme TEXT DEFAULT 'light',
    language TEXT DEFAULT 'en'
  );
`);

// ── Users ─────────────────────────────────────────────────────────────────────

const insertUser = (username, password, is_pro = 0) => {
  try {
    db.prepare('INSERT INTO users (username, password, is_pro) VALUES (?, ?, ?)').run(username, password, is_pro);
  } catch (e) {}
};

const findUser = (username, password) => {
  return db.prepare('SELECT * FROM users WHERE username = ? AND password = ?').get(username, password);
};

const getUserById = (id) => {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(id);
};

const getUserByUsername = (username) => {
  return db.prepare('SELECT * FROM users WHERE username = ?').get(username);
};

const updateProfile = (userId, displayName, email) => {
  db.prepare('UPDATE users SET display_name = ?, email = ? WHERE id = ?').run(displayName, email, userId);
};

// ── Categories ────────────────────────────────────────────────────────────────

const insertCategory = (id, name) => {
  try {
    db.prepare('INSERT INTO categories (id, name) VALUES (?, ?)').run(id, name);
  } catch (e) {}
};

const getCategories = () => {
  return db.prepare('SELECT * FROM categories').all();
};

// ── Products ──────────────────────────────────────────────────────────────────

const insertProduct = (name, category_id) => {
  try {
    db.prepare('INSERT INTO products (name, category_id) VALUES (?, ?)').run(name, category_id);
  } catch (e) {}
};

const getProduct = (id) => {
  return db.prepare('SELECT * FROM products WHERE id = ?').get(id);
};

// TODO: add ORDER BY + OFFSET once we exceed first-page display limits
const listProducts = ({ page, limit, categoryId }) => {
  const offset = (page - 1) * limit;
  if (categoryId) {
    return db.prepare('SELECT * FROM products WHERE category_id = ? LIMIT ? OFFSET ?').all(categoryId, limit, offset);
  }
  return db.prepare('SELECT * FROM products LIMIT ? OFFSET ?').all(limit, offset);
};

const search = (query) => {
  const q = `%${query}%`;
  return db.prepare('SELECT * FROM products WHERE name LIKE ?').all(q);
};

// ── Files ─────────────────────────────────────────────────────────────────────

const uploadFile = (userId, filename, fileId) => {
  return db.prepare('INSERT INTO files (user_id, filename, file_id) VALUES (?, ?, ?)').run(userId, filename, fileId);
};

const getFile = (fileId) => {
  return db.prepare('SELECT * FROM files WHERE file_id = ?').get(fileId);
};

const getUserFiles = (userId) => {
  return db.prepare('SELECT * FROM files WHERE user_id = ?').all(userId);
};

// ── Audit ─────────────────────────────────────────────────────────────────────

const insertAudit = (userId, action, detail) => {
  db.prepare('INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)').run(userId, action, detail);
};

const getAudit = (userId, offset, limit) => {
  return db.prepare('SELECT * FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?').all(userId, limit, offset);
};

// ── Settings ──────────────────────────────────────────────────────────────────

const getUserSettings = (userId) => {
  return db.prepare('SELECT * FROM user_settings WHERE user_id = ?').get(userId);
};

const saveUserSettings = (userId, updates) => {
  const existing = getUserSettings(userId);
  if (!existing) {
    db.prepare('INSERT INTO user_settings (user_id, notifications, theme, language) VALUES (?, ?, ?, ?)').run(
      userId,
      updates.notifications !== undefined ? (updates.notifications ? 1 : 0) : 1,
      updates.theme || 'light',
      updates.language || 'en'
    );
  } else {
    if (updates.notifications !== undefined) {
      db.prepare('UPDATE user_settings SET notifications = ? WHERE user_id = ?').run(updates.notifications ? 1 : 0, userId);
    }
    if (updates.theme) {
      db.prepare('UPDATE user_settings SET theme = ? WHERE user_id = ?').run(updates.theme, userId);
    }
    if (updates.language) {
      db.prepare('UPDATE user_settings SET language = ? WHERE user_id = ?').run(updates.language, userId);
    }
  }
};

module.exports = {
  insertUser,
  findUser,
  getUserById,
  getUserByUsername,
  updateProfile,
  insertCategory,
  getCategories,
  insertProduct,
  getProduct,
  listProducts,
  search,
  uploadFile,
  getFile,
  getUserFiles,
  insertAudit,
  getAudit,
  getUserSettings,
  saveUserSettings,
};