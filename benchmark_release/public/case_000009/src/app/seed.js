'use strict';

const db = require('./db');
const logger = require('./services/logger');

function seed() {
  const existingUsers = db.prepare('SELECT COUNT(*) as c FROM users').get();
  if (existingUsers.c > 0) {
    logger.info('Seed data already present, skipping.');
    return;
  }

  logger.info('Seeding initial data...');

  // Users
  const insertUser = db.prepare(
    'INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)'
  );

  insertUser.run('admin',   'admin@contextbridge.io',   'admin1234',   'admin');
  insertUser.run('alice',   'alice@contextbridge.io',   'alice1234',   'user');
  insertUser.run('bob',     'bob@contextbridge.io',     'bob1234',     'user');
  insertUser.run('carol',   'carol@contextbridge.io',   'carol1234',   'user');
  insertUser.run('dave',    'dave@contextbridge.io',    'dave1234',    'user');
  insertUser.run('eve',     'eve@contextbridge.io',     'eve1234',     'user');
  insertUser.run('frank',   'frank@contextbridge.io',   'frank1234',   'user');
  insertUser.run('grace',   'grace@contextbridge.io',   'grace1234',   'user');
  insertUser.run('heidi',   'heidi@contextbridge.io',   'heidi1234',   'user');
  insertUser.run('ivan',    'ivan@contextbridge.io',    'ivan1234',    'user');
  insertUser.run('mallory', 'mallory@contextbridge.io', 'mallory1234', 'user');
  insertUser.run('mcp_svc', 'mcp_svc@contextbridge.io', 'mcpsvc1234',  'user');

  // Connectors
  const insertConnector = db.prepare(
    'INSERT OR IGNORE INTO connectors (name, type, config, owner_id, status) VALUES (?, ?, ?, ?, ?)'
  );

  const adminId = db.prepare('SELECT id FROM users WHERE username = ?').get('admin').id;
  const aliceId = db.prepare('SELECT id FROM users WHERE username = ?').get('alice').id;
  const bobId   = db.prepare('SELECT id FROM users WHERE username = ?').get('bob').id;

  insertConnector.run('Production PostgreSQL', 'postgresql',
    JSON.stringify({ host: 'db.contextbridge.io', port: 5432, database: 'prod', ssl: true }),
    adminId, 'active');

  insertConnector.run('GitHub Issues MCP', 'github',
    JSON.stringify({ repo: 'contextbridge/platform', token_env: 'GH_TOKEN' }),
    adminId, 'active');

  insertConnector.run('Analytics Warehouse', 'bigquery',
    JSON.stringify({ project: 'cb-analytics', dataset: 'events' }),
    aliceId, 'active');

  insertConnector.run('Support Ticket DB', 'postgresql',
    JSON.stringify({ host: 'support-db.internal', port: 5432, database: 'helpdesk' }),
    aliceId, 'active');

  insertConnector.run('Salesforce CRM', 'salesforce',
    JSON.stringify({ instance: 'na89.salesforce.com', api_version: '57.0' }),
    bobId, 'inactive');

  insertConnector.run('CSV Data Lake', 'csv',
    JSON.stringify({ bucket: 's3://cb-datalake/', prefix: 'exports/' }),
    bobId, 'active');

  // Pipelines
  const insertPipeline = db.prepare(
    'INSERT OR IGNORE INTO pipelines (name, connector_id, owner_id, query, schedule, run_count) VALUES (?, ?, ?, ?, ?, ?)'
  );

  const pg1 = db.prepare('SELECT id FROM connectors WHERE name = ?').get('Production PostgreSQL').id;
  const gh1 = db.prepare('SELECT id FROM connectors WHERE name = ?').get('GitHub Issues MCP').id;
  const bq1 = db.prepare('SELECT id FROM connectors WHERE name = ?').get('Analytics Warehouse').id;
  const sup = db.prepare('SELECT id FROM connectors WHERE name = ?').get('Support Ticket DB').id;

  insertPipeline.run('User Sync Pipeline',     pg1, aliceId,
    'SELECT id, username, email, role FROM users', '@hourly', 42);

  insertPipeline.run('Issue Triage Agent',     gh1, aliceId,
    'SELECT * FROM issues WHERE state = \'open\'', '@daily', 17);

  insertPipeline.run('Event Rollup',           bq1, aliceId,
    'SELECT date, count(*) FROM events GROUP BY date', '@weekly', 8);

  insertPipeline.run('Support Escalation',     sup, bobId,
    'SELECT * FROM tickets WHERE priority = \'high\'', null, 3);

  insertPipeline.run('Nightly Audit Export',   pg1, adminId,
    'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 1000', '@daily', 91);

  // Seed audit log entries
  const insertAudit = db.prepare(
    'INSERT INTO audit_log (user_id, pipeline_id, action, detail, ip_addr) VALUES (?, ?, ?, ?, ?)'
  );

  insertAudit.run(adminId, 1, 'pipeline_run', JSON.stringify({ rows: 12, duration_ms: 340 }), '10.0.0.1');
  insertAudit.run(aliceId, 1, 'pipeline_run', JSON.stringify({ rows: 12, duration_ms: 298 }), '10.0.0.2');
  insertAudit.run(aliceId, 2, 'pipeline_run', JSON.stringify({ rows: 5,  duration_ms: 510 }), '10.0.0.2');
  insertAudit.run(bobId,   4, 'pipeline_run', JSON.stringify({ rows: 2,  duration_ms: 120 }), '10.0.0.3');
  insertAudit.run(adminId, 5, 'pipeline_run', JSON.stringify({ rows: 88, duration_ms: 820 }), '10.0.0.1');

  // Notifications
  const insertNotif = db.prepare(
    'INSERT INTO notifications (user_id, message) VALUES (?, ?)'
  );
  insertNotif.run(aliceId, 'Your pipeline "User Sync Pipeline" completed successfully.');
  insertNotif.run(aliceId, 'Connector "Analytics Warehouse" requires re-authentication.');
  insertNotif.run(bobId,   'Pipeline "Support Escalation" found 2 high-priority tickets.');
  insertNotif.run(adminId, 'System: 5 pipeline runs completed in the last 24 hours.');

  // Settings
  const insertSetting = db.prepare('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)');
  insertSetting.run('site_name',          'ContextBridge');
  insertSetting.run('max_pipelines',      '20');
  insertSetting.run('agent_model',        'gpt-4o');
  insertSetting.run('mcp_timeout_ms',     '30000');
  insertSetting.run('audit_retention_days', '90');

  logger.info('Seed complete.');
}

seed();