'use strict';

const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const { getDb } = require('./database');

const db = getDb();

const SALT_ROUNDS = 10;

const users = [
  { username: 'alice', email: 'alice@collab.io', password: process.env.SEED_ALICE_PASSWORD || crypto.randomBytes(18).toString('base64url'), role: 'admin' },
  { username: 'bob', email: 'bob@collab.io', password: process.env.SEED_BOB_PASSWORD || crypto.randomBytes(18).toString('base64url'), role: 'user' },
  { username: 'charlie', email: 'charlie@collab.io', password: process.env.SEED_CHARLIE_PASSWORD || crypto.randomBytes(18).toString('base64url'), role: 'user' },
  { username: 'diana', email: 'diana@collab.io', password: process.env.SEED_DIANA_PASSWORD || crypto.randomBytes(18).toString('base64url'), role: 'user' },
  { username: 'eve', email: 'eve@collab.io', password: process.env.SEED_EVE_PASSWORD || crypto.randomBytes(18).toString('base64url'), role: 'user' },
];

const cardTemplates = [
  { title: 'Q1 2025 OKRs', content: '<h2>Objectives</h2><ul><li>Grow ARR by 40%</li><li>Reduce churn to 3%</li></ul>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Onboarding Checklist', content: '<h3>Day 1</h3><p>Setup laptop, VPN, Slack.</p><h3>Week 1</h3><p>Meet the team, read runbooks.</p>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Product Roadmap', content: '<p><strong>Phase 1:</strong> Core editor improvements</p><p><strong>Phase 2:</strong> Real-time collaboration</p>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Release Notes v2.4', content: '<h2>What\'s New</h2><ul><li>Dark mode</li><li>Export to PDF</li><li>Improved search</li></ul>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Team Retrospective', content: '<h3>Went Well</h3><p>Shipped on time.</p><h3>Improvements</h3><p>Better async comms.</p>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Architecture Decision Record #12', content: '<p>Use PostgreSQL for production. SQLite for local dev.</p>', is_public: 0, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Component Library Docs', content: '<x-button>Primary</x-button><x-card>Sample card content</x-card>', is_public: 1, allow_custom_elements: 1, template_mode: 0 },
  { title: 'Template Gallery', content: '<p>Use <code>${name}</code> and <code>${date}</code> placeholders.</p>', is_public: 1, allow_custom_elements: 0, template_mode: 1 },
  { title: 'Design System Overview', content: '<h2>Colors</h2><p>Primary: #0066CC</p><h2>Typography</h2><p>Inter, 16px base</p>', is_public: 1, allow_custom_elements: 1, template_mode: 1 },
  { title: 'API Integration Guide', content: '<pre>POST /api/cards\nContent-Type: application/json\n{"title":"...","content":"..."}</pre>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
  { title: 'Bug Tracker Embed', content: '<x-issue-list project="core" status="open"></x-issue-list>', is_public: 0, allow_custom_elements: 1, template_mode: 1 },
  { title: 'Marketing Copy Draft', content: '<h1>Build Together</h1><p>CollabDocs lets your team create rich content in real-time.</p>', is_public: 1, allow_custom_elements: 0, template_mode: 0 },
];

function seed() {
  const existing = db.prepare('SELECT COUNT(*) as cnt FROM users').get();
  if (existing.cnt > 0) {
    console.log('[seed] Database already seeded, skipping.');
    return;
  }

  const insertUser = db.prepare(`
    INSERT INTO users (username, email, password_hash, role)
    VALUES (@username, @email, @password_hash, @role)
  `);

  const userIds = [];
  for (const u of users) {
    const hash = bcrypt.hashSync(u.password, SALT_ROUNDS);
    const result = insertUser.run({ username: u.username, email: u.email, password_hash: hash, role: u.role });
    userIds.push(result.lastInsertRowid);
  }

  const insertCard = db.prepare(`
    INSERT INTO cards (user_id, title, content, is_public, allow_custom_elements, template_mode)
    VALUES (@user_id, @title, @content, @is_public, @allow_custom_elements, @template_mode)
  `);

  for (let i = 0; i < cardTemplates.length; i++) {
    const tpl = cardTemplates[i];
    const owner = userIds[i % userIds.length];
    insertCard.run({ user_id: owner, ...tpl });
  }

  console.log(`[seed] Inserted ${users.length} users and ${cardTemplates.length} cards.`);
}

seed();
