'use strict';

const bcrypt = require('bcryptjs');
const { v4: uuidv4 } = require('uuid');
const { initDb, getDb } = require('./db');

initDb();
const db = getDb();

// Seed users
const users = [
  { username: 'alice', email: 'alice@dataviz.io', password: 'AlicePass123!', role: 'admin' },
  { username: 'bob', email: 'bob@dataviz.io', password: 'BobPass123!', role: 'editor' },
  { username: 'charlie', email: 'charlie@dataviz.io', password: 'CharliePass123!', role: 'viewer' },
  { username: 'diana', email: 'diana@dataviz.io', password: 'DianaPass456!', role: 'editor' },
  { username: 'eve', email: 'eve@dataviz.io', password: 'EvePass789!', role: 'viewer' },
];

const insertUser = db.prepare(`
  INSERT OR IGNORE INTO users (username, email, password_hash, role)
  VALUES (?, ?, ?, ?)
`);

for (const u of users) {
  const hash = bcrypt.hashSync(u.password, 10);
  insertUser.run(u.username, u.email, hash, u.role);
}

// Get user IDs
const aliceId = db.prepare('SELECT id FROM users WHERE username = ?').get('alice').id;
const bobId = db.prepare('SELECT id FROM users WHERE username = ?').get('bob').id;
const charlieId = db.prepare('SELECT id FROM users WHERE username = ?').get('charlie').id;
const dianaId = db.prepare('SELECT id FROM users WHERE username = ?').get('diana').id;

const insertDashboard = db.prepare(`
  INSERT OR IGNORE INTO dashboards (id, user_id, title, description, chart_config, is_public)
  VALUES (?, ?, ?, ?, ?, ?)
`);

// Seed dashboards
const dashboards = [
  {
    id: uuidv4(), user_id: aliceId,
    title: 'Q4 Revenue Overview',
    description: 'Monthly revenue breakdown for Q4 2024 across all product lines.',
    chart_config: JSON.stringify({ type: 'bar', data: [120, 340, 290, 410], labels: ['Oct', 'Nov', 'Dec', 'Jan'] }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: aliceId,
    title: 'User Retention Funnel',
    description: 'Tracks user retention from signup through 90-day engagement.',
    chart_config: JSON.stringify({ type: 'funnel', stages: ['Signup', '7-day', '30-day', '90-day'], values: [10000, 6200, 3800, 2100] }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: bobId,
    title: 'Infrastructure Cost Analysis',
    description: 'Breakdown of monthly cloud spend by service category.',
    chart_config: JSON.stringify({ type: 'pie', categories: ['Compute', 'Storage', 'Network', 'Support'], values: [45, 25, 20, 10] }),
    is_public: 0
  },
  {
    id: uuidv4(), user_id: bobId,
    title: 'API Latency P99',
    description: 'P99 latency metrics across all API endpoints over the past 30 days.',
    chart_config: JSON.stringify({ type: 'line', interval: 'daily', endpoints: ['/api/query', '/api/render', '/api/export'] }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: charlieId,
    title: 'Sales Pipeline Status',
    description: 'Current state of active deals in the sales pipeline.',
    chart_config: JSON.stringify({ type: 'kanban', columns: ['Prospect', 'Qualified', 'Proposal', 'Closed'] }),
    is_public: 0
  },
  {
    id: uuidv4(), user_id: dianaId,
    title: 'Marketing Campaign ROI',
    description: 'Return on investment per marketing channel for H1 2025.',
    chart_config: JSON.stringify({ type: 'bar', channels: ['Email', 'Paid Search', 'Social', 'Organic'], roi: [3.2, 1.8, 2.4, 5.1] }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: dianaId,
    title: 'Customer Segment Breakdown',
    description: 'Distribution of customers by segment and contract value.',
    chart_config: JSON.stringify({ type: 'treemap', segments: ['Enterprise', 'Mid-Market', 'SMB', 'Startup'] }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: aliceId,
    title: 'Churn Risk Heatmap',
    description: 'Heatmap of churn risk scores grouped by tenure and usage frequency.',
    chart_config: JSON.stringify({ type: 'heatmap', x: 'tenure_months', y: 'weekly_logins', metric: 'churn_risk' }),
    is_public: 0
  },
  {
    id: uuidv4(), user_id: bobId,
    title: 'Deploy Frequency by Team',
    description: 'Number of production deployments per engineering team per week.',
    chart_config: JSON.stringify({ type: 'bar', teams: ['Platform', 'Frontend', 'Backend', 'Data'], weeks: 12 }),
    is_public: 1
  },
  {
    id: uuidv4(), user_id: charlieId,
    title: 'NPS Trend 2024',
    description: 'Net Promoter Score trend over all quarters of 2024.',
    chart_config: JSON.stringify({ type: 'line', quarters: ['Q1', 'Q2', 'Q3', 'Q4'], scores: [42, 48, 51, 56] }),
    is_public: 1
  },
];

for (const d of dashboards) {
  insertDashboard.run(d.id, d.user_id, d.title, d.description, d.chart_config, d.is_public);
}

// Seed some comments
const insertComment = db.prepare(`
  INSERT OR IGNORE INTO comments (dashboard_id, user_id, body)
  VALUES (?, ?, ?)
`);

const pubDash = db.prepare('SELECT id FROM dashboards WHERE is_public = 1 LIMIT 1').get();
if (pubDash) {
  insertComment.run(pubDash.id, bobId, 'Great breakdown — can we add a YoY comparison?');
  insertComment.run(pubDash.id, charlieId, 'Numbers look off for November. Check the ETL job?');
  insertComment.run(pubDash.id, dianaId, 'Shared this with the exec team. Very useful.');
}

// Seed audit log
const insertAudit = db.prepare(`
  INSERT INTO audit_log (user_id, action, resource, ip)
  VALUES (?, ?, ?, ?)
`);
insertAudit.run(aliceId, 'LOGIN', null, '10.0.1.5');
insertAudit.run(bobId, 'CREATE_DASHBOARD', 'dashboards', '10.0.1.12');
insertAudit.run(aliceId, 'EXPORT_DASHBOARD', 'dashboards', '10.0.1.5');
insertAudit.run(charlieId, 'VIEW_DASHBOARD', 'dashboards', '10.0.1.99');

console.log('[SEED] Database seeded successfully');
process.exit(0);