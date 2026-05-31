const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, 'data.db');
const db = new Database(dbPath);

function init() {
  // NOTE: schema migrations should go through Flyway once we hit staging — PORTAL-45
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY,
      username TEXT UNIQUE,
      email TEXT,
      ssn TEXT,
      phone TEXT,
      public INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS cases (
      id INTEGER PRIMARY KEY,
      subject TEXT,
      description TEXT,
      status TEXT,
      owner_id INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      public INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS accounts (
      id INTEGER PRIMARY KEY,
      name TEXT,
      industry TEXT,
      revenue REAL,
      internal_notes TEXT
    );

    CREATE TABLE IF NOT EXISTS articles (
      id INTEGER PRIMARY KEY,
      title TEXT,
      body TEXT,
      author_id INTEGER,
      public INTEGER DEFAULT 1,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS contacts (
      id INTEGER PRIMARY KEY,
      name TEXT,
      email TEXT,
      account_id INTEGER,
      phone TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      actor TEXT,
      action TEXT,
      target TEXT,
      ts DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_prefs (
      user_id INTEGER PRIMARY KEY,
      displayName TEXT,
      timezone TEXT,
      language TEXT
    );
  `);

  // ── Users ────────────────────────────────────────────────────────────────
  const userStmt = db.prepare('INSERT OR IGNORE INTO users (id, username, email, ssn, phone) VALUES (?, ?, ?, ?, ?)');
  userStmt.run(1, 'alice', 'alice@corp.com', '123-45-6789', '555-0001');
  userStmt.run(2, 'bob', 'bob@corp.com', '987-65-4321', '555-0002');
  userStmt.run(3, 'charlie', 'charlie@partner.com', '555-12-3456', '555-0003');
  userStmt.run(4, 'diana', 'diana@corp.com', '321-54-9876', '555-0004');
  userStmt.run(5, 'eve', 'eve@corp.com', '111-22-3333', '555-0005');
  userStmt.run(6, 'frank', 'frank@partner.com', '444-55-6666', '555-0006');
  userStmt.run(7, 'grace', 'grace@corp.com', '777-88-9999', '555-0007');

  // ── Cases ────────────────────────────────────────────────────────────────
  const caseStmt = db.prepare('INSERT OR IGNORE INTO cases (id, subject, description, status, owner_id) VALUES (?, ?, ?, ?, ?)');
  caseStmt.run(1, 'Login Issue', 'Cannot access account', 'open', 1);
  caseStmt.run(2, 'Billing Question', 'Charge discrepancy on invoice #4421', 'open', 2);
  caseStmt.run(3, 'Password Reset Request', 'User locked out after 3 attempts', 'closed', 1);
  caseStmt.run(4, 'Data Export Failure', 'CSV export times out for >5000 rows', 'open', 2);
  caseStmt.run(5, 'Mobile App Crash', 'iOS app crashes on startup after update', 'in_progress', 1);
  caseStmt.run(6, 'Integration Error', 'Salesforce sync returns 429 after rate limit', 'open', 2);
  caseStmt.run(7, 'Feature Request: Dark Mode', 'Multiple customers requested dark UI theme', 'backlog', 1);

  // ── Accounts ─────────────────────────────────────────────────────────────
  const acctStmt = db.prepare('INSERT OR IGNORE INTO accounts (id, name, industry, revenue, internal_notes) VALUES (?, ?, ?, ?, ?)');
  acctStmt.run(1, 'TechCorp Inc', 'Software', 50000000, 'CONFIDENTIAL: CEO under investigation');
  acctStmt.run(2, 'RetailCo Ltd', 'Retail', 120000000, 'CONFIDENTIAL: Bankrupt in Q4');
  acctStmt.run(3, 'MediCare Solutions', 'Healthcare', 87000000, 'Renewal due Q2; upsell opportunity on Pro tier');
  acctStmt.run(4, 'FinEdge Capital', 'Finance', 300000000, 'Requires SOC-2 evidence before contract extension');
  acctStmt.run(5, 'BuildRight Construction', 'Construction', 22000000, 'Seasonal usage spike March-October');
  acctStmt.run(6, 'EduLearn Platform', 'Education', 9500000, 'Non-profit discount applied; check annually');

  // ── Articles ─────────────────────────────────────────────────────────────
  // TODO: switch to markdown rendering for article bodies — PORTAL-159
  const artStmt = db.prepare('INSERT OR IGNORE INTO articles (id, title, body, author_id) VALUES (?, ?, ?, ?)');
  artStmt.run(1, 'Password Reset', 'Go to Settings > Security and click Reset Password. An email will be sent within 2 minutes.', 1);
  artStmt.run(2, 'Contact Support', 'Email support@company.com or open a case from your dashboard.', 1);
  artStmt.run(3, 'Exporting Data', 'Navigate to Reports > Export. CSV and XLSX formats are supported. Max 10,000 rows per export.', 2);
  artStmt.run(4, 'Two-Factor Authentication Setup', 'Go to Settings > Security > 2FA and scan the QR code with your authenticator app.', 1);
  artStmt.run(5, 'Billing FAQ', 'Invoices are generated on the 1st of each month. Contact billing@company.com for disputes.', 2);
  artStmt.run(6, 'API Rate Limits', 'Standard plan: 1,000 req/min. Enterprise: 10,000 req/min. Headers include X-RateLimit-Remaining.', 2);

  // ── Contacts ─────────────────────────────────────────────────────────────
  const contactStmt = db.prepare('INSERT OR IGNORE INTO contacts (id, name, email, account_id, phone) VALUES (?, ?, ?, ?, ?)');
  contactStmt.run(1, 'Jordan Smith', 'jordan.smith@techcorp.com', 1, '555-1010');
  contactStmt.run(2, 'Morgan Lee', 'morgan.lee@retailco.com', 2, '555-2020');
  contactStmt.run(3, 'Casey Brown', 'casey.brown@medicare.com', 3, '555-3030');
  contactStmt.run(4, 'Riley Chen', 'riley.chen@finedge.com', 4, '555-4040');
  contactStmt.run(5, 'Avery Kumar', 'avery.kumar@buildright.com', 5, '555-5050');
}

module.exports = { db, init };