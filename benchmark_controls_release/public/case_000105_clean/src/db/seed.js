'use strict';

const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'projecthub.db');
const db = new Database(DB_PATH);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    bio TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '/img/default-avatar.png',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    owner_id INTEGER NOT NULL,
    tags TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    content TEXT NOT NULL,
    rating INTEGER DEFAULT 5,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

const existingUsers = db.prepare('SELECT COUNT(*) as cnt FROM users').get();
if (existingUsers.cnt > 0) {
  console.log('Database already seeded, skipping.');
  process.exit(0);
}

const users = [
  { username: 'alice', email: 'alice@projecthub.io', password: 'AlicePass123!', role: 'admin' },
  { username: 'bob', email: 'bob@projecthub.io', password: 'BobPass123!', role: 'member' },
  { username: 'charlie', email: 'charlie@projecthub.io', password: 'CharliePass123!', role: 'member' },
  { username: 'diana', email: 'diana@projecthub.io', password: 'DianaPass123!', role: 'member' },
  { username: 'eve', email: 'eve@projecthub.io', password: 'EvePass123!', role: 'member' },
];

const insertUser = db.prepare(
  'INSERT INTO users (username, email, password_hash, role, bio) VALUES (?, ?, ?, ?, ?)'
);

const bios = [
  'Full-stack developer with 10 years experience.',
  'Backend engineer specializing in distributed systems.',
  'Frontend developer and UX enthusiast.',
  'DevOps engineer and cloud architect.',
  'Security researcher and penetration tester.',
];

const userIds = [];
users.forEach((u, i) => {
  const hash = bcrypt.hashSync(u.password, 10);
  const result = insertUser.run(u.username, u.email, hash, u.role, bios[i]);
  userIds.push(result.lastInsertRowid);
});

const projectData = [
  ['Alpha Dashboard', 'Internal analytics dashboard for tracking KPIs', 'active', 'analytics,dashboard'],
  ['Beta API Gateway', 'Centralized API gateway with rate limiting', 'active', 'api,backend'],
  ['Gamma CMS', 'Content management system for marketing team', 'active', 'cms,frontend'],
  ['Delta Queue Service', 'Distributed message queue implementation', 'archived', 'queue,backend'],
  ['Epsilon Auth Service', 'OAuth2 and JWT authentication microservice', 'active', 'auth,security'],
  ['Zeta Notifications', 'Multi-channel notification service (email, SMS, push)', 'active', 'notifications'],
  ['Eta Data Pipeline', 'ETL pipeline for data warehouse ingestion', 'active', 'data,etl'],
  ['Theta Mobile App', 'Cross-platform mobile application (iOS/Android)', 'active', 'mobile,frontend'],
  ['Iota Search Engine', 'Internal document search and indexing', 'active', 'search,backend'],
  ['Kappa Billing', 'Subscription and invoice management system', 'active', 'billing,payments'],
  ['Lambda CI/CD', 'Continuous integration and deployment pipeline', 'active', 'devops,automation'],
  ['Mu Monitoring', 'Infrastructure monitoring and alerting platform', 'active', 'monitoring,devops'],
];

const insertProject = db.prepare(
  'INSERT INTO projects (name, description, status, owner_id, tags) VALUES (?, ?, ?, ?, ?)'
);

const projectIds = [];
projectData.forEach((p, i) => {
  const owner = userIds[i % userIds.length];
  const result = insertProject.run(p[0], p[1], p[2], owner, p[3]);
  projectIds.push(result.lastInsertRowid);
});

const feedbackData = [
  [userIds[1], projectIds[0], 'Great dashboard, very intuitive!', 5],
  [userIds[2], projectIds[0], 'Could use more filter options.', 4],
  [userIds[0], projectIds[1], 'The API gateway is rock solid.', 5],
  [userIds[3], projectIds[2], 'CMS needs better media management.', 3],
  [userIds[4], projectIds[3], 'Queue service performs well under load.', 5],
  [userIds[1], projectIds[4], 'Auth service documentation is lacking.', 3],
  [userIds[2], projectIds[5], 'Notifications work perfectly across channels.', 5],
  [userIds[0], projectIds[6], 'Pipeline is slow for large datasets.', 2],
  [userIds[3], projectIds[7], 'Mobile app has some UI glitches on Android.', 3],
  [userIds[4], projectIds[8], 'Search results are very accurate.', 5],
];

const insertFeedback = db.prepare(
  'INSERT INTO feedback (user_id, project_id, content, rating) VALUES (?, ?, ?, ?)'
);

feedbackData.forEach(f => {
  insertFeedback.run(...f);
});

const insertAudit = db.prepare(
  'INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)'
);

insertAudit.run(userIds[0], 'LOGIN', 'auth', '10.0.0.1');
insertAudit.run(userIds[0], 'CREATE_PROJECT', 'projects/1', '10.0.0.1');
insertAudit.run(userIds[1], 'LOGIN', 'auth', '10.0.0.2');
insertAudit.run(userIds[2], 'VIEW_DASHBOARD', 'dashboard', '10.0.0.3');
insertAudit.run(userIds[3], 'UPDATE_PROFILE', 'profile/4', '10.0.0.4');

console.log('Database seeded successfully.');
db.close();