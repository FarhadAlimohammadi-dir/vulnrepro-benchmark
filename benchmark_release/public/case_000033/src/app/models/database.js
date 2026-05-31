const Database = require('better-sqlite3');
const path = require('path');
const logger = require('../services/logger');

const dbPath = process.env.DB_PATH || path.join(__dirname, '../../data/auth.db');
let db;

function initDb() {
  try {
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    
    // Users table
    db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    // Sessions table
    db.exec(`
      CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);
    
    // FXAuth tokens table
    db.exec(`
      CREATE TABLE IF NOT EXISTS fxauth_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        app_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);
    
    // Linked accounts table
    db.exec(`
      CREATE TABLE IF NOT EXISTS linked_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        platform_user_id TEXT NOT NULL,
        verified BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, platform, platform_user_id)
      )
    `);
    
    // Audit log table
    db.exec(`
      CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);
    
    // Payment methods table
    db.exec(`
      CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        payment_type TEXT NOT NULL,
        last_four TEXT,
        is_default BOOLEAN DEFAULT 0,
        verified BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);
    
    // Billing history table
    db.exec(`
      CREATE TABLE IF NOT EXISTS billing_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount DECIMAL(10, 2),
        currency TEXT DEFAULT 'USD',
        status TEXT,
        description TEXT,
        transaction_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);
    
    logger.info('Database initialized successfully');
  } catch (error) {
    logger.error(`Database initialization failed: ${error.message}`);
    throw error;
  }
}

function getDb() {
  if (!db) {
    initDb();
  }
  return db;
}

module.exports = {
  initDb,
  getDb
};