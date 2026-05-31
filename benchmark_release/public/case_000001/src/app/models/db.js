'use strict';

const Database = require('better-sqlite3');
const crypto = require('crypto');
const path = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '..', 'nexusrelay.db');
let db;

function initDb() {
  db = new Database(DB_PATH);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      display_name TEXT,
      email TEXT,
      password_hash TEXT NOT NULL,
      salt TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user',
      avatar_initials TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      last_login TEXT
    );

    CREATE TABLE IF NOT EXISTS workflows (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      description TEXT,
      trigger_type TEXT DEFAULT 'manual',
      schedule TEXT,
      status TEXT DEFAULT 'active',
      run_count INTEGER DEFAULT 0,
      last_run TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS workflow_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      workflow_id INTEGER NOT NULL,
      actor TEXT,
      status TEXT DEFAULT 'ok',
      output TEXT,
      ran_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    );

    CREATE TABLE IF NOT EXISTS plugins (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      url TEXT NOT NULL,
      owner_id INTEGER NOT NULL,
      enabled INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS webhooks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      url TEXT NOT NULL,
      events TEXT,
      owner_id INTEGER NOT NULL,
      active INTEGER DEFAULT 1,
      last_delivery TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS exec_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      command TEXT,
      output TEXT,
      actor TEXT,
      exit_code INTEGER DEFAULT 0,
      ran_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      actor TEXT,
      action TEXT,
      target TEXT,
      detail TEXT,
      ip TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      message TEXT,
      read INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
  `);

  _seedData();
  console.log('[db] Database ready:', DB_PATH);
}

function hashPassword(password, salt) {
  return crypto.createHash('sha256').update(password + salt).digest('hex');
}

function _seedUsers() {
  const users = [
    { username: 'alice',   display: 'Alice Chen',    email: 'alice@nexusrelay.io',   password: 'hunter2',    role: 'admin',    initials: 'AC' },
    { username: 'bob',     display: 'Bob Martins',   email: 'bob@nexusrelay.io',     password: 'relay123',   role: 'user',     initials: 'BM' },
    { username: 'carol',   display: 'Carol Okafor',  email: 'carol@nexusrelay.io',   password: 'workflow!',  role: 'user',     initials: 'CO' },
    { username: 'dave',    display: 'Dave Singh',    email: 'dave@nexusrelay.io',    password: 'gateway99',  role: 'user',     initials: 'DS' },
    { username: 'eve',     display: 'Eve Tanaka',    email: 'eve@nexusrelay.io',     password: 'nexus2024',  role: 'operator', initials: 'ET' },
  ];
  for (const u of users) {
    const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(u.username);
    if (!existing) {
      const salt = crypto.randomBytes(16).toString('hex');
      const hash = hashPassword(u.password, salt);
      db.prepare(`INSERT INTO users (username, display_name, email, password_hash, salt, role, avatar_initials)
                  VALUES (?,?,?,?,?,?,?)`).run(u.username, u.display, u.email, hash, salt, u.role, u.initials);
    }
  }
}

function _seedWorkflows() {
  const wfCount = db.prepare('SELECT COUNT(*) as c FROM workflows').get().c;
  if (wfCount > 0) return;

  const alice = db.prepare('SELECT id FROM users WHERE username = ?').get('alice');
  const bob   = db.prepare('SELECT id FROM users WHERE username = ?').get('bob');
  const carol = db.prepare('SELECT id FROM users WHERE username = ?').get('carol');
  const dave  = db.prepare('SELECT id FROM users WHERE username = ?').get('dave');

  const wfs = [
    { owner: alice.id, name: 'Morning Digest',        desc: 'Summarises overnight Slack messages',         trigger: 'schedule', sched: '0 8 * * 1-5', runs: 142 },
    { owner: alice.id, name: 'Deploy Notifier',        desc: 'Posts deploy events to #team-deploys channel', trigger: 'webhook',  sched: null,          runs: 87  },
    { owner: alice.id, name: 'Incident Escalation',    desc: 'Pages on-call when PagerDuty threshold hit',   trigger: 'schedule', sched: '*/5 * * * *', runs: 12  },
    { owner: bob.id,   name: 'Expense Sync',           desc: 'Pulls receipts from Gmail into Notion',        trigger: 'schedule', sched: '0 9 * * 1',   runs: 29  },
    { owner: bob.id,   name: 'PR Review Reminder',     desc: 'Nudges stale GitHub pull requests daily',      trigger: 'schedule', sched: '0 10 * * 1-5',runs: 64  },
    { owner: bob.id,   name: 'Dependency Audit',       desc: 'Runs npm audit and files Jira tickets',        trigger: 'manual',   sched: null,          runs: 8   },
    { owner: carol.id, name: 'Social Media Monitor',   desc: 'Tracks brand mentions across platforms',       trigger: 'schedule', sched: '0 */2 * * *', runs: 201 },
    { owner: carol.id, name: 'Invoice Generator',      desc: 'Creates invoices from Stripe charge events',   trigger: 'webhook',  sched: null,          runs: 55  },
    { owner: dave.id,  name: 'Log Archiver',           desc: 'Compresses and ships logs to S3 nightly',      trigger: 'schedule', sched: '0 2 * * *',   runs: 90  },
    { owner: dave.id,  name: 'Backup Verifier',        desc: 'Validates nightly database backups',           trigger: 'schedule', sched: '30 3 * * *',  runs: 45  },
  ];

  const stmt = db.prepare(`INSERT INTO workflows (owner_id, name, description, trigger_type, schedule, run_count)
                            VALUES (?,?,?,?,?,?)`);
  for (const w of wfs) {
    stmt.run(w.owner, w.name, w.desc, w.trigger, w.sched, w.runs);
  }
}

function _seedAuditLog() {
  const cnt = db.prepare('SELECT COUNT(*) as c FROM audit_log').get().c;
  if (cnt > 0) return;
  const entries = [
    ['alice',  'login',            'session',      '{}',                        '10.0.0.1'],
    ['alice',  'workflow.create',  'workflow:1',   '{"name":"Morning Digest"}', '10.0.0.1'],
    ['bob',    'login',            'session',      '{}',                        '10.0.0.2'],
    ['bob',    'workflow.create',  'workflow:4',   '{"name":"Expense Sync"}',   '10.0.0.2'],
    ['carol',  'login',            'session',      '{}',                        '10.0.0.3'],
    ['alice',  'settings.update',  'gateway',      '{"url":"changed"}',         '10.0.0.1'],
    ['eve',    'login',            'session',      '{}',                        '10.0.0.5'],
    ['dave',   'workflow.run',     'workflow:9',   '{"status":"ok"}',           '10.0.0.4'],
    ['alice',  'plugin.register',  'plugin',       '{"name":"GitLab"}',         '10.0.0.1'],
    ['bob',    'exec.run',         'exec_log:1',   '{"cmd":"ls"}',              '10.0.0.2'],
  ];
  const stmt = db.prepare(`INSERT INTO audit_log (actor, action, target, detail, ip) VALUES (?,?,?,?,?)`);
  for (const e of entries) stmt.run(...e);
}

function _seedNotifications() {
  const cnt = db.prepare('SELECT COUNT(*) as c FROM notifications').get().c;
  if (cnt > 0) return;
  const bob = db.prepare('SELECT id FROM users WHERE username = ?').get('bob');
  if (!bob) return;
  const msgs = [
    'Workflow "Expense Sync" completed successfully.',
    'Gateway connection re-established after brief outage.',
    'Your API token was last used 2 hours ago.',
    'New plugin version available: GitLab 2.3.1',
  ];
  const stmt = db.prepare(`INSERT INTO notifications (user_id, message) VALUES (?,?)`);
  for (const m of msgs) stmt.run(bob.id, m);
}

function _seedData() {
  _seedUsers();
  _seedWorkflows();
  _seedAuditLog();
  _seedNotifications();
}

function getDb() { return db; }

module.exports = { initDb, getDb, hashPassword };