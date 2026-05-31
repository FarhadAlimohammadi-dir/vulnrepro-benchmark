'use strict';

const Database = require('better-sqlite3');
const path = require('path');
const policyEngine = require('./services/policyEngine');
const crypto = require('crypto');

const dbPath = path.join(__dirname, 'data.db');
const db = new Database(dbPath);

function initializeDb() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      email TEXT,
      displayName TEXT,
      role TEXT DEFAULT 'viewer',
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      lastLogin DATETIME
    );

    CREATE TABLE IF NOT EXISTS buckets (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      region TEXT DEFAULT 'us-east-1',
      ownerId INTEGER,
      policy TEXT,
      acl TEXT,
      versioning INTEGER DEFAULT 0,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(ownerId) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS objects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      bucketId TEXT NOT NULL,
      key TEXT NOT NULL,
      content TEXT,
      contentType TEXT DEFAULT 'text/plain',
      size INTEGER DEFAULT 0,
      etag TEXT,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(bucketId) REFERENCES buckets(id),
      UNIQUE(bucketId, key)
    );

    CREATE TABLE IF NOT EXISTS auditLog (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      userId INTEGER,
      action TEXT,
      resource TEXT,
      ipAddress TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tags (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      resourceType TEXT NOT NULL,
      resourceId TEXT NOT NULL,
      tagKey TEXT NOT NULL,
      tagValue TEXT
    );
  `);

  seedData();
}

function seedData() {
  // Seed users
  const users = [
    { username: 'admin', password: 'admin123', email: 'admin@cloudvault.internal', displayName: 'System Administrator', role: 'admin' },
    { username: 'engineer', password: 'eng123', email: 'engineer@cloudvault.internal', displayName: 'Platform Engineer', role: 'engineer' },
    { username: 'viewer', password: 'view123', email: 'viewer@cloudvault.internal', displayName: 'Read-Only Viewer', role: 'viewer' },
    { username: 'alice', password: 'alice2024', email: 'alice@example.com', displayName: 'Alice Nguyen', role: 'engineer' },
    { username: 'bob', password: 'bob2024', email: 'bob@example.com', displayName: 'Bob Martinez', role: 'viewer' },
    { username: 'charlie', password: 'charlie2024', email: 'charlie@example.com', displayName: 'Charlie Osei', role: 'viewer' },
  ];

  const insertUser = db.prepare(`
    INSERT OR IGNORE INTO users (username, password, email, displayName, role)
    VALUES (@username, @password, @email, @displayName, @role)
  `);
  for (const u of users) insertUser.run(u);

  // Seed buckets: demo bucket uses the broad-access policy from policyEngine
  const demoPolicy = policyEngine.createDefaultBucketPolicy('demo-bucket');
  const demoPolicyStr = JSON.stringify(demoPolicy).replace(/'/g, "''");

  const privatePolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'AllowOwnerOnly',
        Effect: 'Allow',
        Principal: { AWS: 'arn:aws:iam::123456789012:root' },
        Action: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
        Resource: 'arn:aws:s3:::private-assets/*'
      }
    ]
  }).replace(/'/g, "''");

  const logsPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'AllowLogsService',
        Effect: 'Allow',
        Principal: { Service: 'logging.amazonaws.com' },
        Action: ['s3:PutObject'],
        Resource: 'arn:aws:s3:::app-logs/*'
      }
    ]
  }).replace(/'/g, "''");

  db.exec(`
    INSERT OR IGNORE INTO buckets (id, name, region, ownerId, policy, acl) VALUES
      ('demo', 'demo-bucket', 'us-east-1', 1, '${demoPolicyStr}', '{"owner":"admin","grants":[]}'),
      ('private-assets', 'private-assets', 'us-west-2', 1, '${privatePolicy}', '{"owner":"admin","grants":[]}'),
      ('app-logs', 'app-logs', 'us-east-1', 2, '${logsPolicy}', '{"owner":"engineer","grants":[]}'),
      ('backups-prod', 'backups-prod', 'eu-west-1', 1, '{"Version":"2012-10-17","Statement":[]}', '{"owner":"admin","grants":[]}'),
      ('static-web', 'static-web', 'us-east-1', 2, '{"Version":"2012-10-17","Statement":[]}', '{"owner":"engineer","grants":[]}');
  `);

  // Seed objects in demo bucket
  const demoObjects = [
    { key: 'public-doc.txt', content: 'This document describes the CloudVault public API v2.', contentType: 'text/plain' },
    { key: 'secret-doc.txt', content: 'CONFIDENTIAL: Q4 financial projections show $50M revenue target. Do not distribute.', contentType: 'text/plain' },
    { key: 'customer-data.csv', content: 'customer_id,email,phone\n1,alice@example.com,555-1234\n2,bob@example.com,555-5678\n3,carol@example.com,555-9012', contentType: 'text/csv' },
    { key: 'internal-memo.txt', content: 'INTERNAL: Acquisition of CompanyX valued at $500M approved by board. Embargo until Q1 announcement.', contentType: 'text/plain' },
    { key: 'api-keys.json', content: '{"stripe_key":"sk_test_4eC39HqLyjWDarjtT1zdp7dc","sendgrid":"SG.noreply","internal_token":"cvt-prod-8f2a91b"}', contentType: 'application/json' },
    { key: 'deployment-config.yml', content: 'environment: production\ndatabase_url: postgres://prod-db.internal:5432/cloudvault\nredis_url: redis://cache.internal:6379', contentType: 'text/yaml' },
  ];

  const insertObj = db.prepare(`
    INSERT OR IGNORE INTO objects (bucketId, key, content, contentType, size, etag)
    VALUES (@bucketId, @key, @content, @contentType, @size, @etag)
  `);
  for (const o of demoObjects) {
    insertObj.run({
      bucketId: 'demo',
      key: o.key,
      content: o.content,
      contentType: o.contentType,
      size: o.content.length,
      etag: `"${crypto.createHash('md5').update(o.content).digest('hex')}"`
    });
  }

  // Seed objects in private-assets bucket
  const privateObjects = [
    { key: 'logo-v2.png', content: '[binary PNG data placeholder]', contentType: 'image/png' },
    { key: 'brand-guide.pdf', content: '[binary PDF data placeholder]', contentType: 'application/pdf' },
    { key: 'fonts/inter-regular.woff2', content: '[binary font data placeholder]', contentType: 'font/woff2' },
  ];
  for (const o of privateObjects) {
    insertObj.run({
      bucketId: 'private-assets',
      key: o.key,
      content: o.content,
      contentType: o.contentType,
      size: o.content.length,
      etag: `"${crypto.createHash('md5').update(o.content).digest('hex')}"`
    });
  }

  // Seed audit log entries
  const insertAudit = db.prepare(`
    INSERT OR IGNORE INTO auditLog (id, userId, action, resource, ipAddress, timestamp)
    VALUES (@id, @userId, @action, @resource, @ipAddress, @timestamp)
  `);
  const auditEntries = [
    { id: 1, userId: 1, action: 'AUTH_LOGIN', resource: 'user:admin', ipAddress: '10.0.0.1', timestamp: '2024-11-01 08:12:00' },
    { id: 2, userId: 1, action: 'BUCKET_CREATE', resource: 'bucket:demo', ipAddress: '10.0.0.1', timestamp: '2024-11-01 08:13:00' },
    { id: 3, userId: 2, action: 'AUTH_LOGIN', resource: 'user:engineer', ipAddress: '10.0.0.5', timestamp: '2024-11-01 09:00:00' },
    { id: 4, userId: 2, action: 'OBJECT_PUT', resource: 'bucket:demo/key:public-doc.txt', ipAddress: '10.0.0.5', timestamp: '2024-11-01 09:05:00' },
    { id: 5, userId: 1, action: 'POLICY_UPDATE', resource: 'bucket:demo', ipAddress: '10.0.0.1', timestamp: '2024-11-01 09:30:00' },
    { id: 6, userId: 3, action: 'AUTH_LOGIN', resource: 'user:viewer', ipAddress: '10.0.0.9', timestamp: '2024-11-02 10:00:00' },
    { id: 7, userId: 2, action: 'OBJECT_PUT', resource: 'bucket:app-logs/key:2024-11-02.log', ipAddress: '10.0.0.5', timestamp: '2024-11-02 10:15:00' },
    { id: 8, userId: 1, action: 'USER_ROLE_UPDATE', resource: 'user:3:role:viewer', ipAddress: '10.0.0.1', timestamp: '2024-11-03 14:00:00' },
  ];
  for (const e of auditEntries) insertAudit.run(e);
}

// ── User queries ──────────────────────────────────────────────────────────────
function getUserByCredentials(username, password) {
  return db.prepare('SELECT * FROM users WHERE username = ? AND password = ?').get(username, password);
}

function getUserById(id) {
  return db.prepare('SELECT id, username, email, displayName, role, createdAt, lastLogin FROM users WHERE id = ?').get(id);
}

function listUsers() {
  return db.prepare('SELECT id, username, email, displayName, role, createdAt FROM users ORDER BY id').all();
}

function updateUserProfile(userId, { email, displayName }) {
  db.prepare('UPDATE users SET email = COALESCE(@email, email), displayName = COALESCE(@displayName, displayName) WHERE id = @id')
    .run({ email: email || null, displayName: displayName || null, id: userId });
}

function updateUserRole(userId, role) {
  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, userId);
}

// ── Bucket queries ────────────────────────────────────────────────────────────
function listBuckets() {
  return db.prepare('SELECT id, name, region, createdAt FROM buckets ORDER BY createdAt DESC').all();
}

function listBucketsPaginated(limit, offset) {
  const buckets = db.prepare('SELECT id, name, region, createdAt FROM buckets ORDER BY createdAt DESC LIMIT ? OFFSET ?').all(limit, offset);
  const { total } = db.prepare('SELECT COUNT(*) as total FROM buckets').get();
  return { buckets, total };
}

function getBucket(bucketId) {
  return db.prepare('SELECT * FROM buckets WHERE id = ?').get(bucketId);
}

function updateBucketPolicy(bucketId, policy) {
  db.prepare('UPDATE buckets SET policy = ? WHERE id = ?').run(policy, bucketId);
}

function updateBucketAcl(bucketId, acl) {
  db.prepare('UPDATE buckets SET acl = ? WHERE id = ?').run(acl, bucketId);
}

function deleteBucket(bucketId) {
  db.prepare('DELETE FROM objects WHERE bucketId = ?').run(bucketId);
  db.prepare('DELETE FROM buckets WHERE id = ?').run(bucketId);
}

function getBucketStats(bucketId) {
  const { count, totalSize } = db.prepare(
    'SELECT COUNT(*) as count, COALESCE(SUM(size),0) as totalSize FROM objects WHERE bucketId = ?'
  ).get(bucketId);
  return { bucketId, objectCount: count, totalSize };
}

// ── Object queries ────────────────────────────────────────────────────────────
function listObjects(bucketId) {
  return db.prepare('SELECT key, size, contentType, createdAt FROM objects WHERE bucketId = ? ORDER BY key').all(bucketId);
}

function getObject(bucketId, objectKey) {
  return db.prepare('SELECT * FROM objects WHERE bucketId = ? AND key = ?').get(bucketId, objectKey);
}

function putObject(bucketId, key, content, contentType, etag) {
  db.prepare(`
    INSERT INTO objects (bucketId, key, content, contentType, size, etag)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(bucketId, key) DO UPDATE SET
      content = excluded.content,
      contentType = excluded.contentType,
      size = excluded.size,
      etag = excluded.etag,
      updatedAt = CURRENT_TIMESTAMP
  `).run(bucketId, key, content, contentType, content.length, etag);
}

function deleteObject(bucketId, key) {
  db.prepare('DELETE FROM objects WHERE bucketId = ? AND key = ?').run(bucketId, key);
}

// ── Audit log queries ─────────────────────────────────────────────────────────
function insertAuditLog(userId, action, resource, ipAddress) {
  db.prepare('INSERT INTO auditLog (userId, action, resource, ipAddress) VALUES (?, ?, ?, ?)').run(userId, action, resource, ipAddress || null);
}

function getRecentAuditLogs(limit, offset) {
  return db.prepare(`
    SELECT a.id, a.action, a.resource, a.ipAddress, a.timestamp,
           u.username
    FROM auditLog a
    LEFT JOIN users u ON a.userId = u.id
    ORDER BY a.timestamp DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset || 0);
}

function getUserAuditLogs(userId, limit) {
  return db.prepare(`
    SELECT id, action, resource, ipAddress, timestamp
    FROM auditLog WHERE userId = ?
    ORDER BY timestamp DESC LIMIT ?
  `).all(userId, limit);
}

// ── Storage stats ─────────────────────────────────────────────────────────────
function getStorageStats() {
  const { bucketCount } = db.prepare('SELECT COUNT(*) as bucketCount FROM buckets').get();
  const { objectCount, totalSize } = db.prepare('SELECT COUNT(*) as objectCount, COALESCE(SUM(size),0) as totalSize FROM objects').get();
  return { bucketCount, objectCount, totalSize };
}

// ── Search ────────────────────────────────────────────────────────────────────
function search(query, type) {
  const like = `%${query}%`;
  const results = { buckets: [], objects: [], users: [] };

  if (type === 'all' || type === 'buckets') {
    results.buckets = db.prepare('SELECT id, name, region FROM buckets WHERE name LIKE ? LIMIT 20').all(like);
  }
  if (type === 'all' || type === 'objects') {
    results.objects = db.prepare('SELECT bucketId, key, contentType, size FROM objects WHERE key LIKE ? LIMIT 20').all(like);
  }
  if (type === 'all' || type === 'users') {
    results.users = db.prepare('SELECT id, username, displayName, role FROM users WHERE username LIKE ? OR displayName LIKE ? LIMIT 20').all(like, like);
  }

  return results;
}

module.exports = {
  initializeDb,
  getUserByCredentials,
  getUserById,
  listUsers,
  updateUserProfile,
  updateUserRole,
  listBuckets,
  listBucketsPaginated,
  getBucket,
  updateBucketPolicy,
  updateBucketAcl,
  deleteBucket,
  getBucketStats,
  listObjects,
  getObject,
  putObject,
  deleteObject,
  insertAuditLog,
  getRecentAuditLogs,
  getUserAuditLogs,
  getStorageStats,
  search
};