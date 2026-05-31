'use strict';

const Database = require('better-sqlite3');
const logger = require('../services/logger');

const DB_PATH = process.env.DB_PATH || '/tmp/nexusboard.db';
const db = new Database(DB_PATH);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    email TEXT,
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
  );

  CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS workspace_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    href TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

// ── Seed users ────────────────────────────────────────────────────────────────
const seedUsers = [
  { username: 'alice',   password: 'alice123', role: 'admin',  email: 'alice@nexusboard.io',  display_name: 'Alice Chen' },
  { username: 'bob',     password: 'bob456',   role: 'member', email: 'bob@nexusboard.io',    display_name: 'Bob Martinez' },
  { username: 'carol',   password: 'carol789', role: 'member', email: 'carol@nexusboard.io',  display_name: 'Carol Smith' },
  { username: 'david',   password: 'david321', role: 'viewer', email: 'david@nexusboard.io',  display_name: 'David Park' },
  { username: 'eve',     password: 'eve654',   role: 'member', email: 'eve@nexusboard.io',    display_name: 'Eve Johnson' },
];

const insertUser = db.prepare(
  'INSERT OR IGNORE INTO users (username, password, role, email, display_name) VALUES (?, ?, ?, ?, ?)'
);
for (const u of seedUsers) {
  insertUser.run(u.username, u.password, u.role, u.email, u.display_name);
}

// ── Seed projects ─────────────────────────────────────────────────────────────
const seedProjects = [
  { id: 1, name: 'Alpha Launch',        description: 'Q1 product launch coordination',       owner: 'alice' },
  { id: 2, name: 'Backend Infrastructure', description: 'Kubernetes migration and HA setup', owner: 'alice' },
  { id: 3, name: 'Mobile App v2',       description: 'iOS and Android redesign effort',      owner: 'bob' },
  { id: 4, name: 'Data Pipeline',       description: 'ETL pipeline for analytics warehouse', owner: 'carol' },
  { id: 5, name: 'Security Hardening',  description: 'Annual review and patching cycle',     owner: 'alice' },
  { id: 6, name: 'Customer Portal',     description: 'Self-service portal for enterprise customers', owner: 'bob' },
];

const insertProject = db.prepare(
  'INSERT OR IGNORE INTO projects (id, name, description, owner_id) VALUES (?, ?, ?, (SELECT id FROM users WHERE username=?))'
);
for (const p of seedProjects) {
  insertProject.run(p.id, p.name, p.description, p.owner);
}

// ── Seed tasks ────────────────────────────────────────────────────────────────
const seedTasks = [
  { id: 1,  pid: 1, title: 'Finalise landing page copy',      assignee: 'alice',  priority: 'high' },
  { id: 2,  pid: 1, title: 'Schedule press release',           assignee: 'bob',    priority: 'high' },
  { id: 3,  pid: 1, title: 'Create social media assets',       assignee: 'carol',  priority: 'medium' },
  { id: 4,  pid: 1, title: 'Coordinate beta tester onboarding',assignee: 'eve',    priority: 'low' },
  { id: 5,  pid: 2, title: 'Provision staging cluster',        assignee: 'carol',  priority: 'high' },
  { id: 6,  pid: 2, title: 'Write Helm chart templates',       assignee: 'david',  priority: 'medium' },
  { id: 7,  pid: 2, title: 'Set up monitoring dashboards',     assignee: 'alice',  priority: 'medium' },
  { id: 8,  pid: 3, title: 'Wireframe new navigation',         assignee: 'bob',    priority: 'high' },
  { id: 9,  pid: 3, title: 'Update design tokens',             assignee: 'eve',    priority: 'low' },
  { id: 10, pid: 4, title: 'Define source schema',             assignee: 'carol',  priority: 'high' },
  { id: 11, pid: 4, title: 'Build incremental loader',         assignee: 'david',  priority: 'medium' },
  { id: 12, pid: 5, title: 'Review dependency updates',        assignee: 'alice',  priority: 'high' },
  { id: 13, pid: 5, title: 'Run penetration test report',      assignee: 'alice',  priority: 'high' },
  { id: 14, pid: 6, title: 'Design account settings page',     assignee: 'bob',    priority: 'medium' },
  { id: 15, pid: 6, title: 'Implement SSO callback handler',   assignee: 'carol',  priority: 'high' },
];

const insertTask = db.prepare(
  'INSERT OR IGNORE INTO tasks (id, project_id, title, assignee, priority) VALUES (?, ?, ?, ?, ?)'
);
for (const t of seedTasks) {
  insertTask.run(t.id, t.pid, t.title, t.assignee, t.priority);
}

// ── Seed notifications ────────────────────────────────────────────────────────
const seedNotifs = [
  { id: 1, user: 'alice', msg: 'Project "Alpha Launch" is due for review in 3 days.' },
  { id: 2, user: 'alice', msg: 'Bob completed task: Schedule press release.' },
  { id: 3, user: 'alice', msg: 'New team member Eve Johnson joined NexusBoard.' },
  { id: 4, user: 'bob',   msg: 'You were assigned to task: Wireframe new navigation.' },
  { id: 5, user: 'bob',   msg: 'Carol left a comment on Mobile App v2.' },
  { id: 6, user: 'carol', msg: 'Staging cluster provisioning completed.' },
  { id: 7, user: 'carol', msg: 'Reminder: Data Pipeline schema review tomorrow.' },
  { id: 8, user: 'david', msg: 'You have been granted viewer access to Backend Infrastructure.' },
  { id: 9, user: 'eve',   msg: 'Welcome to NexusBoard! Start by exploring your assigned tasks.' },
];

const insertNotif = db.prepare(
  'INSERT OR IGNORE INTO notifications (id, user_id, message) VALUES (?, (SELECT id FROM users WHERE username=?), ?)'
);
for (const n of seedNotifs) {
  insertNotif.run(n.id, n.user, n.msg);
}

// ── Seed workspace links ──────────────────────────────────────────────────────
const seedLinks = [
  { id: 1, label: 'Documentation Hub',    href: 'https://docs.example.com',          category: 'docs' },
  { id: 2, label: 'Status Page',          href: 'https://status.example.com',        category: 'ops' },
  { id: 3, label: 'CI / CD Pipeline',     href: 'https://ci.example.com',            category: 'devops' },
  { id: 4, label: 'Design System',        href: 'https://design.example.com',        category: 'design' },
  { id: 5, label: 'Runbook Library',      href: 'https://runbooks.example.com',      category: 'ops' },
  { id: 6, label: 'Engineering Blog',     href: 'https://blog.example.com',          category: 'general' },
  { id: 7, label: 'Security Guidelines',  href: 'https://sec.example.com/guidelines',category: 'security' },
];

const insertLink = db.prepare(
  'INSERT OR IGNORE INTO workspace_links (id, label, href, category) VALUES (?, ?, ?, ?)'
);
for (const l of seedLinks) {
  insertLink.run(l.id, l.label, l.href, l.category);
}

// ── Seed audit log ────────────────────────────────────────────────────────────
const seedAudit = [
  { user: 'alice', action: 'project.create',  detail: 'Created project: Alpha Launch' },
  { user: 'alice', action: 'project.create',  detail: 'Created project: Backend Infrastructure' },
  { user: 'bob',   action: 'project.create',  detail: 'Created project: Mobile App v2' },
  { user: 'carol', action: 'task.complete',   detail: 'Completed task #5: Provision staging cluster' },
  { user: 'alice', action: 'user.role_change',detail: 'Set david to role: viewer' },
];

const insertAudit = db.prepare(
  'INSERT OR IGNORE INTO audit_log (user_id, action, detail) VALUES ((SELECT id FROM users WHERE username=?), ?, ?)'
);
for (const a of seedAudit) {
  insertAudit.run(a.user, a.action, a.detail);
}

logger.info(`Database ready at ${DB_PATH}`);

module.exports = db;