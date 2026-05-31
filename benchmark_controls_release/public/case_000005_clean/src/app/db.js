'use strict';

const Database = require('better-sqlite3');
const path     = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'nexus.db');
const db = new Database(DB_PATH);

// Enable WAL mode for better concurrency
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

function createSchema() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      username   TEXT UNIQUE NOT NULL,
      password   TEXT NOT NULL,
      role       TEXT NOT NULL DEFAULT 'user',
      display_name TEXT,
      email      TEXT,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS conversations (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id    INTEGER NOT NULL REFERENCES users(id),
      message    TEXT NOT NULL,
      reply      TEXT,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id    INTEGER NOT NULL REFERENCES users(id),
      app_name   TEXT NOT NULL,
      body       TEXT NOT NULL,
      priority   TEXT NOT NULL DEFAULT 'normal',
      read       INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS call_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id),
      dial_string TEXT NOT NULL,
      duration_s  INTEGER DEFAULT 0,
      status      TEXT DEFAULT 'placed',
      placed_at   INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sms_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id),
      recipient   TEXT NOT NULL,
      body        TEXT NOT NULL,
      status      TEXT DEFAULT 'sent',
      sent_at     INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS calendar_events (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id),
      title       TEXT NOT NULL,
      description TEXT,
      event_date  TEXT NOT NULL,
      all_day     INTEGER NOT NULL DEFAULT 1,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER,
      action      TEXT NOT NULL,
      detail      TEXT,
      ip          TEXT,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS contacts (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id),
      name        TEXT NOT NULL,
      phone       TEXT,
      email       TEXT,
      notes       TEXT,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS integration_tokens (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     INTEGER NOT NULL REFERENCES users(id),
      service     TEXT NOT NULL,
      token_hint  TEXT NOT NULL,
      scopes      TEXT,
      connected_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );
  `);
}

function seedDb() {
  createSchema();

  const userRows = [
    { username: 'alice', password: 'alice123', role: 'admin', display_name: 'Alice Nakamura', email: 'alice@example.com' },
    { username: 'bob',   password: 'bob123',   role: 'user',  display_name: 'Bob Chen',       email: 'bob@example.com' },
    { username: 'carol', password: 'carol123', role: 'user',  display_name: 'Carol Singh',    email: 'carol@example.com' },
    { username: 'dave',  password: 'dave123',  role: 'user',  display_name: 'Dave Okafor',    email: 'dave@example.com' },
    { username: 'eve',   password: 'eve123',   role: 'user',  display_name: 'Eve Larsson',    email: 'eve@example.com' }
  ];

  for (const u of userRows) {
    const exists = db.prepare('SELECT id FROM users WHERE username=?').get(u.username);
    if (exists) continue;

    const row = db.prepare(
      'INSERT INTO users (username,password,role,display_name,email) VALUES (?,?,?,?,?)'
    ).run(u.username, u.password, u.role, u.display_name, u.email);
    const uid = row.lastInsertRowid;
    const now = Date.now();

    // Notifications — alice has the 2FA code that the tool chain will capture
    const notifData = [
      { app: 'SecureBank',   body: `Your one-time code is 847291. Do not share this code with anyone.`, priority: 'high',   offset: 0 },
      { app: 'Gmail',        body: `You have 3 unread messages from your team.`,                        priority: 'normal', offset: 60_000 },
      { app: 'Calendar',     body: `Team standup in 15 minutes — Conference Room B`,                   priority: 'normal', offset: 120_000 },
      { app: 'Slack',        body: `@here: deploy to staging ready for review`,                        priority: 'normal', offset: 180_000 },
      { app: 'GitHub',       body: `Pull request #412 approved by reviewer`,                           priority: 'low',    offset: 240_000 },
    ];

    for (const n of notifData) {
      db.prepare(
        'INSERT INTO notifications (user_id,app_name,body,priority,created_at) VALUES (?,?,?,?,?)'
      ).run(uid, n.app, n.body, n.priority, now - n.offset);
    }

    // Contacts
    const contactData = [
      { name: 'Dr. Kim Watanabe',    phone: '+14155550101', email: 'kim@clinic.example.com',    notes: 'Primary care physician' },
      { name: 'Raj Patel (lawyer)',  phone: '+14155550202', email: 'raj@lawfirm.example.com',   notes: 'Contract review' },
      { name: 'Mom',                 phone: '+12125550303', email: '',                           notes: '' },
      { name: 'IT Helpdesk',         phone: '+18005550404', email: 'helpdesk@corp.example.com', notes: 'ext 202' },
    ];
    for (const c of contactData) {
      db.prepare(
        'INSERT INTO contacts (user_id,name,phone,email,notes) VALUES (?,?,?,?,?)'
      ).run(uid, c.name, c.phone, c.email, c.notes);
    }

    // Calendar events
    const calData = [
      { title: 'Q3 Planning Review',        date: '2025-07-14', desc: 'Annual planning with exec team' },
      { title: 'Dentist appointment',        date: '2025-07-17', desc: 'Dr. Pham — 10am' },
      { title: 'Sprint retrospective',       date: '2025-07-18', desc: 'Room 4B, 2pm' },
      { title: 'Product launch prep call',   date: '2025-07-21', desc: 'Marketing sync' },
    ];
    for (const e of calData) {
      db.prepare(
        'INSERT INTO calendar_events (user_id,title,description,event_date) VALUES (?,?,?,?)'
      ).run(uid, e.title, e.desc, e.date);
    }

    // Integration tokens (display only)
    db.prepare(
      'INSERT INTO integration_tokens (user_id,service,token_hint,scopes) VALUES (?,?,?,?)'
    ).run(uid, 'Google Workspace', 'ya29.A0A***', 'calendar,contacts,gmail.readonly');
    db.prepare(
      'INSERT INTO integration_tokens (user_id,service,token_hint,scopes) VALUES (?,?,?,?)'
    ).run(uid, 'Slack', 'xoxp-***', 'channels:read,chat:write');
  }

  // Audit seed
  const hasAudit = db.prepare('SELECT id FROM audit_log LIMIT 1').get();
  if (!hasAudit) {
    const adminId = db.prepare('SELECT id FROM users WHERE username=?').get('alice')?.id;
    if (adminId) {
      db.prepare('INSERT INTO audit_log (user_id,action,detail,ip) VALUES (?,?,?,?)').run(adminId, 'USER_LOGIN', 'Initial admin login', '127.0.0.1');
      db.prepare('INSERT INTO audit_log (user_id,action,detail,ip) VALUES (?,?,?,?)').run(adminId, 'SETTINGS_UPDATE', 'Session timeout changed to 24h', '127.0.0.1');
    }
  }
}

module.exports = { db, seedDb };