'use strict';

const Database = require('better-sqlite3');
const path     = require('path');
const crypto   = require('crypto');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'nodevault.db');
const db = new Database(DB_PATH);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ── Schema ───────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    email        TEXT UNIQUE NOT NULL,
    password     TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'free',
    role         TEXT NOT NULL DEFAULT 'user',
    api_token    TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS workspaces (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    slug       TEXT UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    user_id      INTEGER NOT NULL REFERENCES users(id),
    role         TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (workspace_id, user_id)
  );

  CREATE TABLE IF NOT EXISTS notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id     INTEGER NOT NULL REFERENCES users(id),
    workspace_id INTEGER REFERENCES workspaces(id),
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    pinned       INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    label   TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

// ── Seed data ────────────────────────────────────────────────────────────────
function seedDb() {
  const existing = db.prepare('SELECT COUNT(*) as n FROM users').get().n;
  if (existing > 0) return;

  const token = () => 'tok_' + crypto.randomBytes(16).toString('hex');

  const insertUser = db.prepare(
    'INSERT INTO users (username, display_name, email, password, plan, role, api_token) VALUES (?, ?, ?, ?, ?, ?, ?)'
  );

  // Seed users
  const users = [
    { username: 'alice',   display: 'Alice Chen',      email: 'alice@nodevault.io',   pw: 'alice123',  plan: 'pro',  role: 'user' },
    { username: 'bob',     display: 'Bob Ramirez',     email: 'bob@nodevault.io',     pw: 'bob456',    plan: 'free', role: 'user' },
    { username: 'carol',   display: 'Carol Nguyen',    email: 'carol@nodevault.io',   pw: 'carol789',  plan: 'pro',  role: 'user' },
    { username: 'dave',    display: 'Dave Kim',        email: 'dave@nodevault.io',    pw: 'dave321',   plan: 'free', role: 'user' },
    { username: 'erin',    display: 'Erin Patel',      email: 'erin@nodevault.io',    pw: 'erin654',   plan: 'pro',  role: 'user' },
    { username: 'frank',   display: 'Frank Osei',      email: 'frank@nodevault.io',   pw: 'frank987',  plan: 'free', role: 'user' },
    { username: 'grace',   display: 'Grace Li',        email: 'grace@nodevault.io',   pw: 'grace111',  plan: 'pro',  role: 'user' },
    { username: 'hector',  display: 'Hector Solis',    email: 'hector@nodevault.io',  pw: 'hector222', plan: 'free', role: 'user' },
    { username: 'ivan',    display: 'Ivan Petrov',     email: 'ivan@nodevault.io',    pw: 'ivan333',   plan: 'free', role: 'user' },
    { username: 'julia',   display: 'Julia Müller',    email: 'julia@nodevault.io',   pw: 'julia444',  plan: 'pro',  role: 'user' },
    { username: 'admin',   display: 'NoteVault Admin', email: 'admin@nodevault.io',   pw: 'adm1n!nv',  plan: 'pro',  role: 'admin' },
  ];

  const tokens = {};
  for (const u of users) {
    const t = token();
    tokens[u.username] = t;
    insertUser.run(u.username, u.display, u.email, u.pw, u.plan, u.role, t);
  }

  // Workspaces
  const insertWs = db.prepare("INSERT INTO workspaces (slug, name) VALUES (?, ?)");
  insertWs.run('team-alpha',   'Team Alpha');
  insertWs.run('design-hub',   'Design Hub');
  insertWs.run('engineering',  'Engineering');
  insertWs.run('marketing',    'Marketing');

  // Workspace members
  const insertMember = db.prepare("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)");
  // team-alpha: alice(1), bob(2), carol(3)
  insertMember.run(1, 1, 'owner');
  insertMember.run(1, 2, 'member');
  insertMember.run(1, 3, 'member');
  // design-hub: carol(3), grace(7), julia(10)
  insertMember.run(2, 3, 'owner');
  insertMember.run(2, 7, 'member');
  insertMember.run(2, 10, 'member');
  // engineering: alice(1), dave(4), frank(6), ivan(9)
  insertMember.run(3, 1, 'owner');
  insertMember.run(3, 4, 'member');
  insertMember.run(3, 6, 'member');
  insertMember.run(3, 9, 'member');
  // marketing: erin(5), hector(8)
  insertMember.run(4, 5, 'owner');
  insertMember.run(4, 8, 'member');

  // Notes
  const insertNote = db.prepare(
    "INSERT INTO notes (owner_id, workspace_id, title, body, pinned, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now', ?))"
  );

  const noteData = [
    [1, 1, 'Welcome to NoteVault', 'Get started by creating your first workspace note. You can format text using Markdown.', 1, '-0 hours'],
    [1, 3, 'Engineering Roadmap Q3', '## Goals\n- Migrate auth to OAuth2\n- Improve search latency\n- Launch mobile app beta', 1, '-1 hours'],
    [1, null, 'Personal reading list', '- Designing Data-Intensive Applications\n- The Staff Engineer\'s Path\n- A Philosophy of Software Design', 0, '-2 hours'],
    [2, 1, 'Team Alpha Sprint Goals', '### Sprint 24\n- [ ] Finish dashboard redesign\n- [ ] API rate limit implementation\n- [ ] E2E test coverage to 80%', 0, '-3 hours'],
    [2, null, 'Bob\'s scratch notes', 'ideas for the retro tomorrow...', 0, '-5 hours'],
    [3, 2, 'Design System Components', '## Components\n- Button variants\n- Form inputs\n- Modal patterns\n- Toast notifications', 1, '-4 hours'],
    [3, 1, 'Meeting notes 2024-06-10', 'Attendees: alice, bob, carol\nAction items: carol to send mockups by EOW', 0, '-6 hours'],
    [4, 3, 'Dev Environment Setup', '1. Install nvm\n2. `nvm use 20`\n3. `npm install`\n4. Copy .env.example → .env', 0, '-8 hours'],
    [5, 4, 'Campaign Brief - Summer Launch', 'Target audience: 25-34 SaaS users\nKey message: Collaboration without chaos', 1, '-2 hours'],
    [5, 4, 'Content calendar draft', 'Week 1: Blog post on remote work tips\nWeek 2: Case study — Team Alpha', 0, '-10 hours'],
    [6, 3, 'On-call runbook', '## Incident response\n1. Check Grafana dashboard\n2. Review last deploy\n3. Page secondary if unresolved after 15m', 1, '-12 hours'],
    [7, 2, 'Brand colour palette', '#1a1a2e, #16213e, #0f3460, #e94560', 0, '-7 hours'],
    [8, 4, 'SEO keyword research', 'collaborative notes, team wiki, shared notepad, knowledge base tool', 0, '-9 hours'],
    [9, 3, 'Infrastructure cost analysis', 'Current monthly: $2,840\nProjected after migration: $1,950\nSavings: ~31%', 0, '-11 hours'],
    [10, 2, 'UX audit findings', '## Critical\n- Contrast ratio fails WCAG AA on buttons\n- No keyboard trap protection on modal\n\n## Minor\n- Inconsistent icon sizing', 1, '-3 hours'],
    [1, null, 'Conference talk outline', '1. Problem statement (5 min)\n2. Architecture overview (15 min)\n3. Demo (10 min)\n4. Q&A (10 min)', 0, '-14 hours'],
    [2, null, 'Grocery list', 'eggs, oat milk, sourdough bread, coffee beans', 0, '-20 hours'],
    [3, null, 'Learning resources', 'Figma advanced: https://...\nMotion design: https://...', 0, '-18 hours'],
    [11, null, 'Admin: platform metrics', 'DAU: 1,240\nMAU: 8,700\nChurn rate: 2.1%', 1, '-1 hours'],
    [11, null, 'Admin: support queue notes', 'Open tickets: 14\nP1: 2 (auth issues)\nP2: 5', 0, '-2 hours'],
  ];

  for (const nd of noteData) {
    insertNote.run(...nd);
  }

  // Tags
  const insertTag = db.prepare("INSERT INTO tags (note_id, label) VALUES (?, ?)");
  insertTag.run(2, 'roadmap');
  insertTag.run(2, 'engineering');
  insertTag.run(6, 'design');
  insertTag.run(9, 'marketing');
  insertTag.run(11, 'ops');

  // Audit log
  const insertAudit = db.prepare(
    "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, ?, ?, datetime('now', ?))"
  );
  insertAudit.run(1, 'login',         'web',            '-30 minutes');
  insertAudit.run(1, 'note_create',   'Engineering Roadmap Q3', '-29 minutes');
  insertAudit.run(2, 'login',         'web',            '-1 hours');
  insertAudit.run(3, 'profile_update','self',           '-2 hours');
  insertAudit.run(5, 'note_create',   'Campaign Brief', '-2 hours');

  console.log('[NoteVault] Database seeded with demo data.');
}

module.exports = { db, seedDb };