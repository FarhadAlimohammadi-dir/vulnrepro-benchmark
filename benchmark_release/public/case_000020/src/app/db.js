'use strict';

const Database = require('better-sqlite3');
const path     = require('path');
const crypto   = require('crypto');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'toolbridge.db');
const db = new Database(DB_PATH);

// ── Schema ────────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE NOT NULL,
    password   TEXT NOT NULL,
    email      TEXT,
    role       TEXT NOT NULL DEFAULT 'user',
    display_name TEXT,
    bio        TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS integrations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id          INTEGER NOT NULL,
    name              TEXT NOT NULL,
    description       TEXT,
    provider_type     TEXT NOT NULL DEFAULT 'custom',
    authorization_url TEXT,
    token_url         TEXT,
    client_id         TEXT,
    scopes            TEXT DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'active',
    last_sync_at      DATETIME,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    ip         TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    message    TEXT NOT NULL,
    read       INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS api_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    token      TEXT NOT NULL,
    label      TEXT,
    last_used  DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

// ── Seed users ────────────────────────────────────────────────────────────────
const seedUsers = [
  { username: 'alice',   password: 'alice123',   email: 'alice@toolbridge.dev',   role: 'user',  display_name: 'Alice Chen',    bio: 'Backend engineer, loves automations.' },
  { username: 'bob',     password: 'bob456',     email: 'bob@toolbridge.dev',     role: 'user',  display_name: 'Bob Martins',   bio: 'DevOps lead.' },
  { username: 'charlie', password: 'charlie789', email: 'charlie@toolbridge.dev', role: 'user',  display_name: 'Charlie Kim',   bio: 'Full-stack developer.' },
  { username: 'diana',   password: 'diana321',   email: 'diana@toolbridge.dev',   role: 'user',  display_name: 'Diana Okafor',  bio: 'Product manager.' },
  { username: 'eve',     password: 'eve654',     email: 'eve@toolbridge.dev',     role: 'user',  display_name: 'Eve Torres',    bio: 'Data engineer.' },
  { username: 'admin',   password: 'admin2024',  email: 'admin@toolbridge.dev',   role: 'admin', display_name: 'Platform Admin', bio: 'Site administrator.' }
];

const insertUser = db.prepare(
  'INSERT OR IGNORE INTO users (username, password, email, role, display_name, bio) VALUES (?, ?, ?, ?, ?, ?)'
);
for (const u of seedUsers) {
  insertUser.run(u.username, u.password, u.email, u.role, u.display_name, u.bio);
}

// ── Seed integrations ─────────────────────────────────────────────────────────
function userId(username) {
  const row = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  return row ? row.id : null;
}

const sampleIntegrations = [
  {
    owner: 'alice',
    name: 'GitHub – toolbridge-app',
    description: 'CI/CD repo access for main monorepo',
    provider_type: 'github',
    authorization_url: 'https://github.com/login/oauth/authorize',
    token_url: 'https://github.com/login/oauth/token',
    client_id: 'gh_client_alice_001',
    scopes: 'repo,read:user',
    status: 'active'
  },
  {
    owner: 'alice',
    name: 'Slack – #engineering',
    description: 'Post deployment notifications to #engineering',
    provider_type: 'slack',
    authorization_url: 'https://slack.com/oauth/v2/authorize',
    token_url: 'https://slack.com/api/oauth.v2.access',
    client_id: 'slack_client_alice_001',
    scopes: 'channels:read,chat:write',
    status: 'active'
  },
  {
    owner: 'alice',
    name: 'Jira Cloud',
    description: 'Sprint board sync',
    provider_type: 'custom',
    authorization_url: 'https://auth.atlassian.com/authorize',
    token_url: 'https://auth.atlassian.com/oauth/token',
    client_id: 'jira_client_alice_001',
    scopes: 'read:jira-work',
    status: 'active'
  },
  {
    owner: 'bob',
    name: 'GitHub – infra-scripts',
    description: 'Infrastructure automation scripts',
    provider_type: 'github',
    authorization_url: 'https://github.com/login/oauth/authorize',
    token_url: 'https://github.com/login/oauth/token',
    client_id: 'gh_client_bob_001',
    scopes: 'repo',
    status: 'active'
  },
  {
    owner: 'bob',
    name: 'PagerDuty',
    description: 'On-call alert forwarding',
    provider_type: 'custom',
    authorization_url: 'https://app.pagerduty.com/oauth/authorize',
    token_url: 'https://app.pagerduty.com/oauth/token',
    client_id: 'pd_client_bob_001',
    scopes: 'read',
    status: 'active'
  },
  {
    owner: 'charlie',
    name: 'Figma',
    description: 'Design file exports',
    provider_type: 'custom',
    authorization_url: 'https://www.figma.com/oauth',
    token_url: 'https://api.figma.com/v1/oauth/token',
    client_id: 'figma_client_charlie_001',
    scopes: 'file_read',
    status: 'active'
  },
  {
    owner: 'charlie',
    name: 'Notion',
    description: 'Docs and project notes sync',
    provider_type: 'custom',
    authorization_url: 'https://api.notion.com/v1/oauth/authorize',
    token_url: 'https://api.notion.com/v1/oauth/token',
    client_id: 'notion_client_charlie_001',
    scopes: 'read_content',
    status: 'inactive'
  },
  {
    owner: 'diana',
    name: 'Salesforce',
    description: 'CRM data bridge for roadmap planning',
    provider_type: 'custom',
    authorization_url: 'https://login.salesforce.com/services/oauth2/authorize',
    token_url: 'https://login.salesforce.com/services/oauth2/token',
    client_id: 'sf_client_diana_001',
    scopes: 'api',
    status: 'active'
  },
  {
    owner: 'eve',
    name: 'Databricks',
    description: 'ETL pipeline trigger',
    provider_type: 'custom',
    authorization_url: 'https://accounts.azuredatabricks.net/oidc/oauth2/v2.0/authorize',
    token_url: 'https://accounts.azuredatabricks.net/oidc/oauth2/v2.0/token',
    client_id: 'db_client_eve_001',
    scopes: 'sql clusters',
    status: 'active'
  }
];

const insertIntegration = db.prepare(`
  INSERT OR IGNORE INTO integrations
    (owner_id, name, description, provider_type, authorization_url, token_url, client_id, scopes, status)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
`);

for (const s of sampleIntegrations) {
  const uid = userId(s.owner);
  if (!uid) continue;
  const exists = db.prepare('SELECT id FROM integrations WHERE owner_id = ? AND name = ?').get(uid, s.name);
  if (!exists) {
    insertIntegration.run(uid, s.name, s.description, s.provider_type, s.authorization_url, s.token_url, s.client_id, s.scopes, s.status);
  }
}

// ── Seed notifications ────────────────────────────────────────────────────────
const aliceId = userId('alice');
if (aliceId) {
  const hasNote = db.prepare('SELECT id FROM notifications WHERE user_id = ?').get(aliceId);
  if (!hasNote) {
    db.prepare("INSERT INTO notifications (user_id, message) VALUES (?, ?)").run(aliceId, 'Welcome to ToolBridge! Connect your first integration to get started.');
    db.prepare("INSERT INTO notifications (user_id, message) VALUES (?, ?)").run(aliceId, 'Your GitHub integration was successfully connected.');
  }
}

// ── Seed API tokens ───────────────────────────────────────────────────────────
const bobId = userId('bob');
if (bobId) {
  const hasToken = db.prepare('SELECT id FROM api_tokens WHERE user_id = ?').get(bobId);
  if (!hasToken) {
    const tok = 'tbk_' + crypto.randomBytes(16).toString('hex');
    db.prepare("INSERT INTO api_tokens (user_id, token, label) VALUES (?, ?, ?)").run(bobId, tok, 'CI pipeline token');
  }
}

module.exports = { db };