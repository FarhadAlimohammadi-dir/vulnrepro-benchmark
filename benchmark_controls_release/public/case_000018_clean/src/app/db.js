'use strict';

const Database = require('better-sqlite3');
const crypto   = require('crypto');
const path     = require('path');

let _db;

function getDb() {
  if (_db) return _db;
  const dbPath = process.env.DB_PATH || path.join(__dirname, 'visionboard.db');
  _db = new Database(dbPath);
  _db.pragma('journal_mode = WAL');
  _db.pragma('foreign_keys = ON');
  initSchema(_db);
  return _db;
}

function hash(pw) {
  return crypto.createHash('sha256').update(pw).digest('hex');
}

function initSchema(db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      username      TEXT    UNIQUE NOT NULL,
      password_hash TEXT    NOT NULL,
      email         TEXT,
      full_name     TEXT,
      plan          TEXT    DEFAULT 'free',
      is_admin      INTEGER DEFAULT 0,
      bio           TEXT,
      avatar_url    TEXT,
      created_at    TEXT    DEFAULT (datetime('now')),
      updated_at    TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS images (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id      INTEGER NOT NULL,
      filename      TEXT    NOT NULL,
      storage_path  TEXT    UNIQUE NOT NULL,
      content_type  TEXT    NOT NULL,
      file_size     INTEGER DEFAULT 0,
      ai_description TEXT,
      ocr_text      TEXT,
      tags          TEXT    DEFAULT '',
      is_public     INTEGER DEFAULT 0,
      created_at    TEXT    DEFAULT (datetime('now')),
      updated_at    TEXT    DEFAULT (datetime('now')),
      FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS shares (
      image_id     INTEGER NOT NULL,
      shared_with  INTEGER NOT NULL,
      created_at   TEXT    DEFAULT (datetime('now')),
      PRIMARY KEY(image_id, shared_with),
      FOREIGN KEY(image_id) REFERENCES images(id),
      FOREIGN KEY(shared_with) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id    INTEGER,
      action     TEXT    NOT NULL,
      entity     TEXT,
      entity_id  INTEGER,
      detail     TEXT,
      ip         TEXT,
      created_at TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS collections (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id    INTEGER NOT NULL,
      name        TEXT    NOT NULL,
      description TEXT,
      created_at  TEXT    DEFAULT (datetime('now')),
      FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS collection_items (
      collection_id INTEGER NOT NULL,
      image_id      INTEGER NOT NULL,
      added_at      TEXT    DEFAULT (datetime('now')),
      PRIMARY KEY(collection_id, image_id),
      FOREIGN KEY(collection_id) REFERENCES collections(id),
      FOREIGN KEY(image_id) REFERENCES images(id)
    );

    CREATE TABLE IF NOT EXISTS comments (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id   INTEGER NOT NULL,
      user_id    INTEGER NOT NULL,
      body       TEXT    NOT NULL,
      created_at TEXT    DEFAULT (datetime('now')),
      FOREIGN KEY(image_id) REFERENCES images(id),
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

  seedData(db);
}

function seedData(db) {
  // ── Users ───────────────────────────────────────────────────────────────────
  const seedUsers = [
    { username: 'alice',   password: 'alice123',  plan: 'pro',      is_admin: 0, full_name: 'Alice Henderson', email: 'alice@example.com',   bio: 'Product designer & photographer.' },
    { username: 'bob',     password: 'bob123',    plan: 'free',     is_admin: 0, full_name: 'Bob Kaminski',   email: 'bob@example.com',     bio: 'Backend engineer, avid runner.' },
    { username: 'carol',   password: 'carol123',  plan: 'free',     is_admin: 0, full_name: 'Carol Nguyen',   email: 'carol@example.com',   bio: 'Data scientist and ML enthusiast.' },
    { username: 'dave',    password: 'dave123',   plan: 'pro',      is_admin: 0, full_name: 'Dave Okonkwo',   email: 'dave@example.com',    bio: 'Freelance illustrator.' },
    { username: 'eve',     password: 'eve123',    plan: 'enterprise',is_admin: 0,full_name: 'Eve Larsson',    email: 'eve@example.com',     bio: 'VP of Engineering, loves hiking.' },
    { username: 'frank',   password: 'frank123',  plan: 'free',     is_admin: 0, full_name: 'Frank Delacroix', email: 'frank@example.com',  bio: 'Content creator.' },
    { username: 'grace',   password: 'grace123',  plan: 'pro',      is_admin: 0, full_name: 'Grace Kim',      email: 'grace@example.com',   bio: 'UX researcher.' },
    { username: 'heidi',   password: 'heidi123',  plan: 'free',     is_admin: 0, full_name: 'Heidi Baum',     email: 'heidi@example.com',   bio: 'Startup founder.' },
    { username: 'ivan',    password: 'ivan123',   plan: 'pro',      is_admin: 0, full_name: 'Ivan Petrov',    email: 'ivan@example.com',    bio: 'Security researcher.' },
    { username: 'admin',   password: 'admin2024', plan: 'enterprise',is_admin: 1,full_name: 'Platform Admin', email: 'admin@example.com',   bio: 'System administrator.' },
  ];

  const upsertUser = db.prepare(`
    INSERT OR IGNORE INTO users (username, password_hash, plan, is_admin, full_name, email, bio)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  for (const u of seedUsers) {
    upsertUser.run(u.username, hash(u.password), u.plan, u.is_admin, u.full_name, u.email, u.bio);
  }

  const alice = db.prepare('SELECT id FROM users WHERE username = ?').get('alice');
  const bob   = db.prepare('SELECT id FROM users WHERE username = ?').get('bob');
  const carol = db.prepare('SELECT id FROM users WHERE username = ?').get('carol');
  const dave  = db.prepare('SELECT id FROM users WHERE username = ?').get('dave');
  const eve   = db.prepare('SELECT id FROM users WHERE username = ?').get('eve');

  if (!alice || !bob || !carol) return;

  // ── Images ───────────────────────────────────────────────────────────────────
  const insertImage = db.prepare(`
    INSERT OR IGNORE INTO images
      (owner_id, filename, storage_path, content_type, file_size, ai_description, ocr_text, tags, is_public)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  // legacy: kept for v1 API clients still in the wild
  insertImage.run(
    alice.id,
    'bank_statement_q3.png',
    '/user-uploads/1/1689251070_ttl1djtdc4jkzne6a5yaj4n7m',
    'image/png', 84320,
    'A financial statement showing account balance of $42,000. Account number 1234-5678. Owner: Alice Henderson.',
    'Balance: $42,000 | Account: 1234-5678 | Q3 2024',
    'finance,private,statement', 0
  );
  insertImage.run(
    alice.id,
    'product_mockup_v3.png',
    '/user-uploads/1/1689300001_m1n2o3p4q5r6s7t8',
    'image/png', 220000,
    'A high-fidelity product mockup showing a mobile app onboarding screen with blue gradient background.',
    null,
    'design,mockup,mobile', 0
  );
  insertImage.run(
    alice.id,
    'team_offsite_2024.jpg',
    '/user-uploads/1/1689400002_a9b8c7d6e5f4g3h2',
    'image/jpeg', 510000,
    'Group photo of approximately 12 people at an outdoor offsite event with mountains in background.',
    null,
    'team,photo,offsite', 1
  );
  insertImage.run(
    alice.id,
    'wireframe_checkout.png',
    '/user-uploads/1/1689500003_i1j2k3l4m5n6o7p8',
    'image/png', 95000,
    'Low-fidelity wireframe showing a three-step checkout flow with cart, payment, and confirmation screens.',
    null,
    'wireframe,ux,checkout', 0
  );

  // Bob's images
  insertImage.run(
    bob.id,
    'team_photo.jpg',
    '/user-uploads/2/default_profile',
    'image/jpeg', 312000,
    'A group photo of a software development team in an open-plan office setting.',
    null,
    'team,photo,office', 1
  );
  insertImage.run(
    bob.id,
    'architecture_diagram.png',
    '/user-uploads/2/1689600004_q1w2e3r4t5y6u7i8',
    'image/png', 77000,
    'System architecture diagram showing microservices connected via an event bus. Three main service clusters visible.',
    null,
    'architecture,engineering,diagram', 0
  );
  insertImage.run(
    bob.id,
    'sprint_board_screenshot.png',
    '/user-uploads/2/1689700005_o9p8a7b6c5d4e3f2',
    'image/png', 145000,
    'Screenshot of a kanban board with three columns: To Do, In Progress, Done. Sprint 42 visible in header.',
    'Sprint 42 | 8 items in progress | 14 completed',
    'agile,sprint,board', 0
  );

  // Carol's images
  insertImage.run(
    carol.id,
    'data_pipeline_flowchart.pdf.png',
    '/user-uploads/3/1689800006_g1h2i3j4k5l6m7n8',
    'image/png', 210000,
    'Flowchart depicting a data ingestion pipeline: raw data → validation → transformation → warehouse.',
    null,
    'data,pipeline,engineering', 0
  );
  insertImage.run(
    carol.id,
    'model_accuracy_chart.png',
    '/user-uploads/3/1689900007_o1p2q3r4s5t6u7v8',
    'image/png', 88000,
    'Line chart showing ML model accuracy over 50 training epochs. Final accuracy 94.3% on validation set.',
    'Epoch 50: Train 96.1% | Val 94.3% | Loss 0.042',
    'ml,chart,accuracy', 1
  );

  // Dave's images
  if (dave) {
    insertImage.run(
      dave.id,
      'illustration_draft_01.png',
      '/user-uploads/4/1690000008_w1x2y3z4a5b6c7d8',
      'image/png', 630000,
      'Digital illustration of a futuristic cityscape at dusk with neon lighting and flying vehicles.',
      null,
      'illustration,art,futurism', 1
    );
    insertImage.run(
      dave.id,
      'logo_concepts_v2.png',
      '/user-uploads/4/1690100009_e1f2g3h4i5j6k7l8',
      'image/png', 105000,
      'Logo concept sheet showing five variations of a stylized letter D with different color palettes.',
      null,
      'logo,branding,design', 0
    );
  }

  // Eve's images
  if (eve) {
    insertImage.run(
      eve.id,
      'roadmap_h2_2024.png',
      '/user-uploads/5/1690200010_m1n2o3p4q5r6s7t8',
      'image/png', 198000,
      'Product roadmap for H2 2024 showing four tracks: Platform, Growth, Monetisation, and Security.',
      null,
      'roadmap,strategy,product', 0
    );
  }

  // ── Collections ──────────────────────────────────────────────────────────────
  const insertCol = db.prepare(`
    INSERT OR IGNORE INTO collections (owner_id, name, description)
    VALUES (?, ?, ?)
  `);
  insertCol.run(alice.id, 'Design Assets', 'All wireframes and mockups for the current project cycle.');
  insertCol.run(alice.id, 'Private Documents', 'Sensitive files for personal reference only.');
  insertCol.run(bob.id,   'Engineering Diagrams', 'Architecture and flow diagrams for the backend.');

  // ── Audit log entries ────────────────────────────────────────────────────────
  const insertAudit = db.prepare(`
    INSERT OR IGNORE INTO audit_log (user_id, action, entity, entity_id, detail, ip)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insertAudit.run(alice.id, 'upload',  'image', 1, 'Uploaded bank_statement_q3.png',       '192.168.1.10');
  insertAudit.run(alice.id, 'upload',  'image', 2, 'Uploaded product_mockup_v3.png',        '192.168.1.10');
  insertAudit.run(bob.id,   'upload',  'image', 5, 'Uploaded team_photo.jpg',               '10.0.0.55');
  insertAudit.run(carol.id, 'upload',  'image', 8, 'Uploaded data_pipeline_flowchart.pdf.png','10.0.0.60');
  insertAudit.run(alice.id, 'analyze', 'image', 1, 'Requested AI analysis for image 1',     '192.168.1.10');
  insertAudit.run(bob.id,   'analyze', 'image', 5, 'Requested AI analysis for image 5',     '10.0.0.55');

  // ── Comments ─────────────────────────────────────────────────────────────────
  const insertComment = db.prepare(`
    INSERT OR IGNORE INTO comments (image_id, user_id, body)
    VALUES (?, ?, ?)
  `);
  insertComment.run(3,  bob.id,   'Great shot! Who organised the offsite?');
  insertComment.run(3,  carol.id, 'Looks like so much fun.');
  insertComment.run(9,  bob.id,   'Impressive convergence curve — what optimiser did you use?');
  insertComment.run(10, alice.id, 'Love the neon palette!');
}

module.exports = { getDb };