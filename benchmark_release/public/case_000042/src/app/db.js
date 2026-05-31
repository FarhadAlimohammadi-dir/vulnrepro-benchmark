const Database = require('better-sqlite3');
const path = require('path');
const crypto = require('crypto');

let db;

function initDb() {
  db = new Database(path.join(__dirname, 'app.db'));
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      name TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
}

function getUser(email, password) {
  try {
    const stmt = db.prepare('SELECT id, email, name FROM users WHERE email = ? AND password = ?');
    return stmt.get(email, password);
  } catch (e) {
    return null;
  }
}

function createUser(email, password, name) {
  try {
    const stmt = db.prepare('INSERT OR IGNORE INTO users (email, password, name) VALUES (?, ?, ?)');
    stmt.run(email, password, name);
  } catch (e) {
    // User may already exist
  }
}

module.exports = { initDb, getUser, createUser };