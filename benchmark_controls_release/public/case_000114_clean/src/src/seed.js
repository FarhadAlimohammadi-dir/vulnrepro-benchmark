'use strict';

const { getDb, initSchema } = require('./db');
const bcrypt = require('bcryptjs');
const { v4: uuidv4 } = require('uuid');

initSchema();
const db = getDb();

const users = [
  { username: 'alice', email: 'alice@doccollab.io', password: 'AlicePass123!', role: 'admin' },
  { username: 'bob', email: 'bob@doccollab.io', password: 'BobPass123!', role: 'user' },
  { username: 'charlie', email: 'charlie@doccollab.io', password: 'CharliePass123!', role: 'user' },
  { username: 'diana', email: 'diana@doccollab.io', password: 'DianaPass456!', role: 'user' },
  { username: 'eve', email: 'eve@doccollab.io', password: 'EvePass789!', role: 'user' },
];

const insertUser = db.prepare(
  'INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)'
);

const userIds = {};
for (const u of users) {
  const hash = bcrypt.hashSync(u.password, 10);
  insertUser.run(u.username, u.email, hash, u.role);
  const row = db.prepare('SELECT id FROM users WHERE username = ?').get(u.username);
  userIds[u.username] = row.id;
}

const sampleDocs = [
  {
    id: uuidv4(),
    owner: 'alice',
    title: 'Q1 2024 Budget Report',
    content: '<h1>Budget Report</h1><p>Total allocated: $500,000</p><ul><li>Engineering: $200k</li><li>Marketing: $150k</li><li>Operations: $150k</li></ul>',
    media_type: 'text/html',
    is_public: 0,
  },
  {
    id: uuidv4(),
    owner: 'alice',
    title: 'Company SVG Logo Spec',
    content: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" fill="blue"/></svg>',
    media_type: 'application/xhtml+xml',
    is_public: 1,
  },
  {
    id: uuidv4(),
    owner: 'bob',
    title: 'Project Roadmap',
    content: '<h2>Roadmap</h2><p>Phase 1: Research<br/>Phase 2: Development<br/>Phase 3: Launch</p>',
    media_type: 'text/html',
    is_public: 0,
  },
  {
    id: uuidv4(),
    owner: 'bob',
    title: 'API Integration Notes',
    content: '<pre><code>GET /api/v2/documents\nAuthorization: Bearer TOKEN\n</code></pre>',
    media_type: 'text/html',
    is_public: 1,
  },
  {
    id: uuidv4(),
    owner: 'charlie',
    title: 'Meeting Notes 2024-03',
    content: '<h3>Weekly Sync</h3><p>Attendees: Alice, Bob, Charlie</p><p>Action items: Review PR #42, Update docs</p>',
    media_type: 'text/html',
    is_public: 0,
  },
  {
    id: uuidv4(),
    owner: 'charlie',
    title: 'XML Schema Definition',
    content: '<?xml version="1.0" encoding="UTF-8"?><schema xmlns="http://www.w3.org/2001/XMLSchema"><element name="doc" type="string"/></schema>',
    media_type: 'application/xhtml+xml',
    is_public: 1,
  },
  {
    id: uuidv4(),
    owner: 'diana',
    title: 'Design Guidelines',
    content: '<h1>Brand Guidelines</h1><p>Primary color: #0066CC</p><p>Font: Inter, 16px</p>',
    media_type: 'text/html',
    is_public: 1,
  },
  {
    id: uuidv4(),
    owner: 'eve',
    title: 'Security Policy Draft',
    content: '<h2>Access Control Policy</h2><p>All users must use MFA. Password rotation every 90 days.</p>',
    media_type: 'text/html',
    is_public: 0,
  },
];

const insertDoc = db.prepare(`
  INSERT OR IGNORE INTO documents (id, owner_id, title, content, sanitized_content, media_type, is_public)
  VALUES (?, ?, ?, ?, ?, ?, ?)
`);

for (const doc of sampleDocs) {
  insertDoc.run(doc.id, userIds[doc.owner], doc.title, doc.content, doc.content, doc.media_type, doc.is_public);
}

// Seed audit log
const insertLog = db.prepare(`
  INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address, details)
  VALUES (?, ?, ?, ?, ?, ?)
`);

const auditEntries = [
  [userIds['alice'], 'LOGIN', null, null, '10.0.0.1', 'Successful login'],
  [userIds['bob'], 'CREATE_DOCUMENT', 'document', sampleDocs[2].id, '10.0.0.2', 'Created Project Roadmap'],
  [userIds['charlie'], 'VIEW_DOCUMENT', 'document', sampleDocs[0].id, '10.0.0.3', 'Viewed Budget Report'],
  [userIds['alice'], 'UPDATE_DOCUMENT', 'document', sampleDocs[0].id, '10.0.0.1', 'Updated budget figures'],
  [userIds['diana'], 'SHARE_DOCUMENT', 'document', sampleDocs[6].id, '10.0.0.4', 'Shared with bob'],
];

for (const entry of auditEntries) {
  insertLog.run(...entry);
}

console.log('Database seeded successfully.');
process.exit(0);