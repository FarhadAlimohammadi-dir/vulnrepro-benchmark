const Database = require('better-sqlite3');
const path = require('path');

// NOTE: WAL mode improves concurrent read performance significantly
const dbPath = path.join(__dirname, 'app.db');
const db = new Database(dbPath);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

module.exports = db;