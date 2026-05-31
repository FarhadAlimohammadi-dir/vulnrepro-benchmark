'use strict';

const bcrypt = require('bcryptjs');
const { getDb } = require('../src/db');

const db = getDb();

// Seed users
const users = [
  { username: 'alice', email: 'alice@example.com', password: 'AlicePass123!', role: 'admin' },
  { username: 'bob', email: 'bob@example.com', password: 'BobPass123!', role: 'editor' },
  { username: 'charlie', email: 'charlie@example.com', password: 'CharliePass123!', role: 'viewer' },
  { username: 'diana', email: 'diana@example.com', password: 'DianaPass123!', role: 'editor' },
  { username: 'eve', email: 'eve@example.com', password: 'EvePass123!', role: 'viewer' },
];

const insertUser = db.prepare(`INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)`);
for (const u of users) {
  insertUser.run(u.username, u.email, bcrypt.hashSync(u.password, 10), u.role);
}

const aliceId = db.prepare('SELECT id FROM users WHERE username = ?').get('alice').id;
const bobId = db.prepare('SELECT id FROM users WHERE username = ?').get('bob').id;
const charlieId = db.prepare('SELECT id FROM users WHERE username = ?').get('charlie').id;

// Seed API specs
const sampleSpecs = [
  {
    title: 'User Management API',
    version: '2.1.0',
    description: 'API for managing users and roles',
    owner_id: aliceId,
    visibility: 'public',
    spec_json: JSON.stringify({
      openapi: '3.0.0',
      info: { title: 'User Management API', version: '2.1.0', description: 'Manage users' },
      paths: {
        '/users': {
          get: {
            operationId: 'listUsers',
            summary: 'List all users',
            tags: ['users'],
            parameters: [
              { name: 'page', in: 'query', type: 'integer', description: 'Page number', default: 1 },
              { name: 'limit', in: 'query', type: 'integer', description: 'Items per page', default: 20 }
            ]
          },
          post: {
            operationId: 'createUser',
            summary: 'Create a user',
            tags: ['users'],
            parameters: [
              { name: 'body', in: 'body', required: true, description: 'User object' }
            ]
          }
        },
        '/users/{id}': {
          get: {
            operationId: 'getUser',
            summary: 'Get user by ID',
            tags: ['users'],
            parameters: [
              { name: 'id', in: 'path', required: true, type: 'integer', description: 'User ID' }
            ]
          }
        }
      }
    })
  },
  {
    title: 'Payment Processing API',
    version: '1.5.2',
    description: 'Internal payment gateway integration',
    owner_id: aliceId,
    visibility: 'private',
    spec_json: JSON.stringify({
      openapi: '3.0.0',
      info: { title: 'Payment Processing API', version: '1.5.2', description: 'Payment gateway' },
      paths: {
        '/payments': {
          post: {
            operationId: 'createPayment',
            summary: 'Initiate a payment',
            tags: ['payments'],
            parameters: [
              { name: 'amount', in: 'body', required: true, type: 'number', description: 'Amount in cents' },
              { name: 'currency', in: 'body', required: true, type: 'string', description: 'Currency code' },
              { name: 'x-idempotency-key', in: 'header', type: 'string', description: 'Idempotency key' }
            ]
          }
        },
        '/payments/{id}/refund': {
          post: {
            operationId: 'refundPayment',
            summary: 'Refund a payment',
            tags: ['payments'],
            parameters: [
              { name: 'id', in: 'path', required: true, type: 'string', description: 'Payment ID' }
            ]
          }
        }
      }
    })
  },
  {
    title: 'Inventory Service API',
    version: '3.0.1',
    description: 'Warehouse inventory management endpoints',
    owner_id: bobId,
    visibility: 'public',
    spec_json: JSON.stringify({
      openapi: '3.0.0',
      info: { title: 'Inventory Service API', version: '3.0.1' },
      paths: {
        '/items': {
          get: {
            operationId: 'listItems',
            summary: 'List inventory items',
            tags: ['inventory'],
            parameters: [
              { name: 'category', in: 'query', type: 'string', description: 'Filter by category' },
              { name: 'in_stock', in: 'query', type: 'boolean', description: 'Only in-stock items' }
            ]
          }
        }
      }
    })
  },
  {
    title: 'Notification API',
    version: '1.0.0',
    description: 'Push notification and email dispatch service',
    owner_id: bobId,
    visibility: 'team',
    spec_json: JSON.stringify({
      openapi: '3.0.0',
      info: { title: 'Notification API', version: '1.0.0' },
      paths: {
        '/notifications': {
          post: {
            operationId: 'sendNotification',
            summary: 'Send notification',
            tags: ['notifications'],
            parameters: [
              { name: 'recipient', in: 'body', required: true, type: 'string', description: 'Recipient ID' },
              { name: 'template', in: 'body', required: true, type: 'string', description: 'Template name' },
              { name: 'channel', in: 'body', type: 'string', description: 'email or push', default: 'email' }
            ]
          }
        }
      }
    })
  },
  {
    title: 'Analytics API',
    version: '2.0.0',
    description: 'Event tracking and analytics aggregation',
    owner_id: charlieId,
    visibility: 'public',
    spec_json: JSON.stringify({
      openapi: '3.0.0',
      info: { title: 'Analytics API', version: '2.0.0' },
      paths: {
        '/events': {
          post: {
            operationId: 'trackEvent',
            summary: 'Track an event',
            tags: ['analytics'],
            parameters: [
              { name: 'event_name', in: 'body', required: true, type: 'string', description: 'Event name' },
              { name: 'properties', in: 'body', type: 'object', description: 'Event properties' }
            ]
          }
        },
        '/reports': {
          get: {
            operationId: 'getReport',
            summary: 'Generate analytics report',
            tags: ['analytics'],
            parameters: [
              { name: 'start_date', in: 'query', required: true, type: 'string', description: 'Start date' },
              { name: 'end_date', in: 'query', required: true, type: 'string', description: 'End date' },
              { name: 'metric', in: 'query', type: 'string', description: 'Metric to report', default: 'pageviews' }
            ]
          }
        }
      }
    })
  }
];

const insertSpec = db.prepare(`INSERT OR IGNORE INTO api_specs (title, version, description, spec_json, owner_id, visibility)
  VALUES (?, ?, ?, ?, ?, ?)`);

for (const s of sampleSpecs) {
  insertSpec.run(s.title, s.version, s.description, s.spec_json, s.owner_id, s.visibility);
}

// Seed some audit log entries
const insertLog = db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
  VALUES (?, ?, ?, ?, ?, ?)`);

const auditEntries = [
  [aliceId, 'login', 'user', aliceId, '{"username":"alice"}', '10.0.0.1'],
  [bobId, 'login', 'user', bobId, '{"username":"bob"}', '10.0.0.2'],
  [aliceId, 'create', 'api_spec', 1, '{"title":"User Management API"}', '10.0.0.1'],
  [aliceId, 'create', 'api_spec', 2, '{"title":"Payment Processing API"}', '10.0.0.1'],
  [bobId, 'create', 'api_spec', 3, '{"title":"Inventory Service API"}', '10.0.0.2'],
  [bobId, 'view_docs', 'api_spec', 1, '{"title":"User Management API"}', '10.0.0.2'],
  [charlieId, 'login', 'user', charlieId, '{"username":"charlie"}', '10.0.0.3'],
  [charlieId, 'view_docs', 'api_spec', 3, '{"title":"Inventory Service API"}', '10.0.0.3'],
  [aliceId, 'update_role', 'user', bobId, '{"newRole":"editor"}', '10.0.0.1'],
  [bobId, 'login', 'user', bobId, '{"username":"bob"}', '10.0.0.4'],
];

for (const entry of auditEntries) {
  try { insertLog.run(...entry); } catch(e) { /* ignore duplicates */ }
}

console.log('[SEED] Database seeded successfully');