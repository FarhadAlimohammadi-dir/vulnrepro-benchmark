'use strict';

const Database = require('better-sqlite3');
const crypto   = require('crypto');

const db = new Database('/data/docvault.db');

// Enable WAL for better concurrent read performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ── Schema ────────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    NOT NULL UNIQUE,
    password     TEXT    NOT NULL,
    role         TEXT    NOT NULL DEFAULT 'user',
    display_name TEXT,
    email        TEXT,
    created_at   INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS documents (
    id           TEXT    PRIMARY KEY,
    filename     TEXT    NOT NULL,
    mimetype     TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    owner_id     INTEGER NOT NULL REFERENCES users(id),
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    tags         TEXT    NOT NULL DEFAULT '',
    created_at   INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS shares (
    token        TEXT    PRIMARY KEY,
    doc_id       TEXT    NOT NULL REFERENCES documents(id),
    created_by   INTEGER NOT NULL REFERENCES users(id),
    expires_at   INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS counters (
    name TEXT PRIMARY KEY,
    val  INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS audit (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    action    TEXT    NOT NULL,
    target    TEXT,
    ip        TEXT,
    ts        INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS comments (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id    TEXT    NOT NULL REFERENCES documents(id),
    user_id   INTEGER NOT NULL REFERENCES users(id),
    body      TEXT    NOT NULL,
    created_at INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_docs_owner   ON documents(owner_id);
  CREATE INDEX IF NOT EXISTS idx_audit_user   ON audit(user_id);
  CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit(ts);
  CREATE INDEX IF NOT EXISTS idx_comments_doc ON comments(doc_id);
`);

// ── Seed users ────────────────────────────────────────────────────────────────
const seedUsers = [
  { username: 'alice',   password: 'alice123',   role: 'user',  display_name: 'Alice Nguyen',    email: 'alice@example.com'   },
  { username: 'bob',     password: 'bob456',     role: 'user',  display_name: 'Bob Martinez',    email: 'bob@example.com'     },
  { username: 'charlie', password: 'charlie789', role: 'admin', display_name: 'Charlie Admin',   email: 'charlie@example.com' },
  { username: 'diana',   password: 'diana999',   role: 'user',  display_name: 'Diana Okonkwo',   email: 'diana@example.com'   },
  { username: 'evan',    password: 'evan555',    role: 'user',  display_name: 'Evan Petrov',     email: 'evan@example.com'    },
];

const now = Math.floor(Date.now() / 1000);
for (const u of seedUsers) {
  try {
    db.prepare(`
      INSERT OR IGNORE INTO users(username, password, role, display_name, email, created_at)
      VALUES (?,?,?,?,?,?)
    `).run(u.username, u.password, u.role, u.display_name, u.email, now);
  } catch (_) { /* already exists */ }
}

// ── Seed counter & bob's initial document ─────────────────────────────────────
// SRE-2031: pre-populate demo content for onboarding; bob's sample report seeds the document store
const existingBobDoc = db.prepare(`
  SELECT d.id FROM documents d
  JOIN users u ON u.id = d.owner_id
  WHERE u.username = 'bob' LIMIT 1
`).get();

if (!existingBobDoc) {
  const bobUser = db.prepare("SELECT id FROM users WHERE username='bob'").get();
  if (bobUser) {
    const ts       = Math.floor(Date.now() / 1000);
    const tsHex    = ts.toString(16).padStart(8, '0');
    const fname    = 'confidential_report.txt';
    const middle   = crypto.createHash('md5').update(String(ts) + fname).digest('hex');
    const uniqPart = ts.toString(16).slice(-4);

    // legacy: seq=101 reserved for initial demo document; new uploads begin at 102+
    db.prepare("INSERT INTO counters(name,val) VALUES('doc_seq',101) ON CONFLICT(name) DO NOTHING").run();
    const docId = `${tsHex}${middle}${uniqPart}-101`;

    db.prepare(`
      INSERT INTO documents(id, filename, mimetype, content, owner_id, size_bytes, tags, created_at)
      VALUES (?,?,?,?,?,?,?,?)
    `).run(
      docId,
      fname,
      'text/plain',
      Buffer.from('SECRET: salary=250000, project=AURORA').toString('base64'),
      bobUser.id,
      38,
      'confidential,hr',
      ts
    );

    // Seed a few more documents for other users so the dashboard looks alive
    const aliceUser   = db.prepare("SELECT id FROM users WHERE username='alice'").get();
    const charlieUser = db.prepare("SELECT id FROM users WHERE username='charlie'").get();
    const dianaUser   = db.prepare("SELECT id FROM users WHERE username='diana'").get();

    const extraDocs = [
      { user: aliceUser,   fname: 'meeting_notes.txt',     content: 'Q3 planning meeting notes. Attendees: Alice, Bob, Charlie.',   tags: 'notes,meetings',   seq: 103 },
      { user: aliceUser,   fname: 'roadmap_2024.txt',      content: 'Product roadmap for 2024. Phase 1: MVP. Phase 2: Scale.',       tags: 'planning',         seq: 104 },
      { user: charlieUser, fname: 'server_inventory.txt',  content: 'web-01: 10.0.0.1\ndb-01: 10.0.0.2\ncache-01: 10.0.0.3',        tags: 'ops,infra',        seq: 105 },
      { user: charlieUser, fname: 'oncall_schedule.txt',   content: 'Week 44: Alice\nWeek 45: Bob\nWeek 46: Charlie',                tags: 'ops',              seq: 106 },
      { user: dianaUser,   fname: 'expense_report.txt',    content: 'Travel: $450\nConference: $1200\nTotal: $1650',                 tags: 'finance',          seq: 107 },
      { user: bobUser,     fname: 'draft_proposal.txt',    content: 'Draft: new caching layer proposal. Status: WIP.',              tags: 'engineering',      seq: 108 },
    ];

    for (const ed of extraDocs) {
      if (!ed.user) continue;
      const ets      = ts - Math.floor(Math.random() * 300);
      const etsHex   = ets.toString(16).padStart(8, '0');
      const emid     = crypto.createHash('md5').update(String(ets) + ed.fname).digest('hex');
      const euniq    = ets.toString(16).slice(-4);
      const edocId   = `${etsHex}${emid}${euniq}-${ed.seq}`;
      const ebuf     = Buffer.from(ed.content).toString('base64');
      try {
        db.prepare(`
          INSERT OR IGNORE INTO documents(id, filename, mimetype, content, owner_id, size_bytes, tags, created_at)
          VALUES (?,?,?,?,?,?,?,?)
        `).run(edocId, ed.fname, 'text/plain', ebuf, ed.user.id, ed.content.length, ed.tags, ets);
      } catch (_) { /* skip */ }
    }

    // Bump counter past all seeded docs
    db.prepare("UPDATE counters SET val=109 WHERE name='doc_seq'").run();
  }
}

module.exports = db;