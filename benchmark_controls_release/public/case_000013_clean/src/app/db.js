'use strict';

const Database = require('better-sqlite3');
const fs       = require('fs');
const path     = require('path');

const DB_PATH = process.env.DB_PATH || '/tmp/devforge.db';
const db      = new Database(DB_PATH);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ── Schema ───────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email        TEXT,
    display_name TEXT,
    role         TEXT NOT NULL DEFAULT 'dev',
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    lang        TEXT NOT NULL DEFAULT 'javascript',
    visibility  TEXT NOT NULL DEFAULT 'private',
    owner_id    INTEGER NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    role       TEXT NOT NULL DEFAULT 'viewer',
    joined_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (user_id)    REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS snippets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title      TEXT NOT NULL,
    lang       TEXT NOT NULL,
    body       TEXT NOT NULL,
    author_id  INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (author_id)  REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS task_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    command    TEXT NOT NULL,
    status     TEXT NOT NULL,
    output     TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (user_id)    REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER,
    actor_name TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    ip         TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// ── Seed helpers ─────────────────────────────────────────────────────────────
const insertUser = db.prepare(`
  INSERT OR IGNORE INTO users (username, password_hash, email, display_name, role)
  VALUES (@username, @password_hash, @email, @display_name, @role)
`);

const seedUsers = [
  { username: 'alice',   password_hash: 'alice123',  email: 'alice@devforge.local',   display_name: 'Alice Admin',    role: 'admin' },
  { username: 'bob',     password_hash: 'bob456',    email: 'bob@devforge.local',     display_name: 'Bob Builder',    role: 'dev'   },
  { username: 'carol',   password_hash: 'carol789',  email: 'carol@devforge.local',   display_name: 'Carol Coder',    role: 'dev'   },
  { username: 'dave',    password_hash: 'dave321',   email: 'dave@devforge.local',    display_name: 'Dave DevOps',    role: 'dev'   },
  { username: 'eve',     password_hash: 'eve654',    email: 'eve@devforge.local',     display_name: 'Eve Engineer',   role: 'dev'   },
];

for (const u of seedUsers) insertUser.run(u);

const alice = db.prepare('SELECT id FROM users WHERE username = ?').get('alice');
const bob   = db.prepare('SELECT id FROM users WHERE username = ?').get('bob');
const carol = db.prepare('SELECT id FROM users WHERE username = ?').get('carol');

const insertProject = db.prepare(`
  INSERT OR IGNORE INTO projects (id, name, description, lang, visibility, owner_id)
  VALUES (@id, @name, @description, @lang, @visibility, @owner_id)
`);

if (alice && bob && carol) {
  const seedProjects = [
    { id: 1, name: 'hello-world',     description: 'Sample starter project for onboarding',      lang: 'javascript', visibility: 'private', owner_id: alice.id },
    { id: 2, name: 'api-gateway',     description: 'Central API gateway service (Node/Express)',  lang: 'javascript', visibility: 'private', owner_id: alice.id },
    { id: 3, name: 'data-pipeline',   description: 'ETL pipeline for analytics warehouse',       lang: 'python',     visibility: 'private', owner_id: bob.id   },
    { id: 4, name: 'ui-components',   description: 'Shared React component library',             lang: 'typescript', visibility: 'private', owner_id: carol.id },
    { id: 5, name: 'auth-service',    description: 'OAuth2/OIDC authentication microservice',    lang: 'go',         visibility: 'private', owner_id: alice.id },
    { id: 6, name: 'cache-layer',     description: 'Redis-backed caching middleware',            lang: 'javascript', visibility: 'private', owner_id: bob.id   },
    { id: 7, name: 'metrics-exporter',description: 'Prometheus metrics exporter for all services',lang: 'go',        visibility: 'private', owner_id: alice.id },
  ];
  for (const p of seedProjects) insertProject.run(p);

  // Seed snippets
  const insertSnippet = db.prepare(`
    INSERT OR IGNORE INTO snippets (project_id, title, lang, body, author_id)
    SELECT @project_id, @title, @lang, @body, @author_id
    WHERE NOT EXISTS (SELECT 1 FROM snippets WHERE project_id = @project_id AND title = @title)
  `);
  insertSnippet.run({ project_id: 1, title: 'Hello World main',   lang: 'javascript', body: 'console.log("hello world");', author_id: alice.id });
  insertSnippet.run({ project_id: 2, title: 'Health check route', lang: 'javascript', body: 'app.get("/health", (req,res)=>res.json({ok:true}));', author_id: alice.id });
  insertSnippet.run({ project_id: 3, title: 'Read CSV helper',    lang: 'python',     body: 'import csv\nwith open("data.csv") as f:\n  reader = csv.DictReader(f)', author_id: bob.id });

  // Seed some task log history
  const insertLog = db.prepare(`
    INSERT OR IGNORE INTO task_logs (project_id, user_id, command, status, output)
    SELECT @project_id, @user_id, @command, @status, @output
    WHERE NOT EXISTS (SELECT 1 FROM task_logs WHERE project_id = @project_id AND command = @command AND user_id = @user_id)
  `);
  insertLog.run({ project_id: 1, user_id: alice.id, command: 'ls -la',            status: 'ok',    output: 'README.md\n' });
  insertLog.run({ project_id: 1, user_id: alice.id, command: 'echo devforge-ok',  status: 'ok',    output: 'devforge-ok\n' });
  insertLog.run({ project_id: 2, user_id: alice.id, command: 'cat README.md',     status: 'ok',    output: 'API service workspace.\n' });
  insertLog.run({ project_id: 3, user_id: bob.id,   command: 'wc -l data.csv',    status: 'error', output: '' });
}

// Write the challenge artifact used for impact demonstration
try {
  fs.writeFileSync('/etc/secret_flag.txt', 'sample_token_redacted\n');
} catch (_) { /* already exists or read-only fs */ }

module.exports = db;