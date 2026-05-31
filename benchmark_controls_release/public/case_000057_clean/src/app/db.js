const Database = require('better-sqlite3');
const crypto = require('crypto');

const db = new Database(':memory:');

// Initialize schema
db.exec(`
  CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  
  CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(username) REFERENCES users(username)
  );
  
  CREATE TABLE portfolios (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    total_balance REAL,
    FOREIGN KEY(username) REFERENCES users(username)
  );
  
  CREATE TABLE holdings (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER,
    symbol TEXT,
    quantity REAL,
    price REAL,
    FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
  );
  
  CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    type TEXT,
    amount REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(username) REFERENCES users(username)
  );
`);

function hashPassword(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

function createUser(username, password, role = 'user') {
  try {
    const stmt = db.prepare('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)');
    stmt.run(username, hashPassword(password), role);
    
    // Create sample portfolio for new user
    const users_stmt = db.prepare('SELECT id FROM users WHERE username = ?');
    const user = users_stmt.get(username);
    
    const portfolio_stmt = db.prepare('INSERT INTO portfolios (username, total_balance) VALUES (?, ?)');
    const pid = portfolio_stmt.run(username, 50000 + Math.random() * 100000).lastInsertRowid;
    
    // Add sample holdings
    const symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN'];
    symbols.forEach(sym => {
      const holdings_stmt = db.prepare('INSERT INTO holdings (portfolio_id, symbol, quantity, price) VALUES (?, ?, ?, ?)');
      holdings_stmt.run(pid, sym, Math.floor(Math.random() * 100), Math.random() * 500);
    });
    
    // Add sample transactions
    for (let i = 0; i < 5; i++) {
      const txn_stmt = db.prepare('INSERT INTO transactions (username, type, amount) VALUES (?, ?, ?)');
      txn_stmt.run(username, Math.random() > 0.5 ? 'BUY' : 'SELL', Math.random() * 10000);
    }
  } catch (e) {
    // User might already exist
  }
}

function authenticateUser(username, password) {
  const stmt = db.prepare('SELECT * FROM users WHERE username = ? AND password_hash = ?');
  return stmt.get(username, hashPassword(password));
}

function createSession(username) {
  const sessionId = crypto.randomBytes(32).toString('hex');
  const stmt = db.prepare('INSERT INTO sessions (id, username) VALUES (?, ?)');
  stmt.run(sessionId, username);
  return sessionId;
}

function getSession(sessionId) {
  if (!sessionId) return null;
  const stmt = db.prepare('SELECT * FROM sessions WHERE id = ?');
  return stmt.get(sessionId);
}

function endSession(sessionId) {
  const stmt = db.prepare('DELETE FROM sessions WHERE id = ?');
  stmt.run(sessionId);
}

function getUser(username) {
  const stmt = db.prepare('SELECT * FROM users WHERE username = ?');
  return stmt.get(username);
}

function getUserPortfolio(username) {
  const portfolio_stmt = db.prepare('SELECT * FROM portfolios WHERE username = ?');
  const portfolio = portfolio_stmt.get(username);
  
  if (!portfolio) return null;
  
  const holdings_stmt = db.prepare('SELECT * FROM holdings WHERE portfolio_id = ?');
  const holdings = holdings_stmt.all(portfolio.id);
  
  return {
    total_balance: portfolio.total_balance,
    holdings: holdings
  };
}

function getTransactionHistory(username) {
  const stmt = db.prepare('SELECT * FROM transactions WHERE username = ? ORDER BY timestamp DESC LIMIT 20');
  return stmt.all(username);
}

module.exports = {
  createUser,
  authenticateUser,
  createSession,
  getSession,
  endSession,
  getUser,
  getUserPortfolio,
  getTransactionHistory
};