'use strict';

const logger = require('../services/logger');

function seedDatabase(db) {
  const existing = db.prepare('SELECT COUNT(*) as cnt FROM users').get();
  if (existing.cnt > 0) {
    logger.info('Database already seeded, skipping');
    return;
  }

  logger.info('Seeding database with initial data...');

  // Seed users
  const users = [
    { id: 'user1', username: 'alice', password: 'alice123', email: 'alice@codeflow.dev', full_name: 'Alice Chen', role: 'admin', bio: 'Platform administrator and OAuth specialist' },
    { id: 'user2', username: 'bob', password: 'bob123', email: 'bob@codeflow.dev', full_name: 'Bob Martinez', role: 'user', bio: 'Full-stack developer building integrations' },
    { id: 'user3', username: 'charlie', password: 'charlie123', email: 'charlie@codeflow.dev', full_name: 'Charlie Kim', role: 'user', bio: 'Backend engineer focused on API security' },
    { id: 'user4', username: 'diana', password: 'diana456', email: 'diana@example.org', full_name: 'Diana Patel', role: 'user', bio: 'Mobile developer integrating OAuth flows' },
    { id: 'user5', username: 'evan', password: 'evan789', email: 'evan@techcorp.io', full_name: 'Evan Russo', role: 'user', bio: 'DevOps engineer managing service accounts' },
    { id: 'user6', username: 'fiona', password: 'fiona321', email: 'fiona@startup.co', full_name: 'Fiona Walsh', role: 'developer', bio: 'Frontend developer, loves React' },
    { id: 'user7', username: 'george', password: 'george654', email: 'george@bigcorp.com', full_name: 'George Okonkwo', role: 'user', bio: 'Enterprise architect' },
    { id: 'user8', username: 'hannah', password: 'hannah987', email: 'hannah@labs.io', full_name: 'Hannah Lee', role: 'developer', bio: 'Security researcher and pen tester' },
  ];

  const insertUser = db.prepare(`
    INSERT INTO users (id, username, password, email, full_name, role, bio, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
  `);

  for (const u of users) {
    try {
      insertUser.run(u.id, u.username, u.password, u.email, u.full_name, u.role, u.bio);
    } catch (e) {
      logger.warn(`Could not insert user ${u.username}: ${e.message}`);
    }
  }

  // Seed OAuth clients
  const clients = [
    {
      id: 'myapp',
      name: 'My Application',
      secret: 'app-secret-key',
      description: 'Primary application integration for CodeFlow platform',
      owner_id: 'user1',
      redirect_uris: JSON.stringify(['https://legitimate-app.com/callback']),
      scopes: 'read write profile',
      website: 'https://legitimate-app.com'
    },
    {
      id: 'dashboard',
      name: 'Analytics Dashboard',
      secret: 'dashboard-secret-8f2a',
      description: 'Internal analytics and reporting dashboard',
      owner_id: 'user1',
      redirect_uris: JSON.stringify(['https://dashboard.codeflow.dev/oauth/callback', 'http://localhost:3000/callback']),
      scopes: 'read profile',
      website: 'https://dashboard.codeflow.dev'
    },
    {
      id: 'mobile-app',
      name: 'CodeFlow Mobile',
      secret: 'mobile-secret-9b3c',
      description: 'iOS and Android mobile application',
      owner_id: 'user2',
      redirect_uris: JSON.stringify(['codeflow://oauth/callback', 'https://mobile.codeflow.dev/callback']),
      scopes: 'read write',
      website: 'https://mobile.codeflow.dev'
    },
    {
      id: 'ci-bot',
      name: 'CI/CD Integration',
      secret: 'cibot-secret-4d7e',
      description: 'Automated pipeline integration for deployment workflows',
      owner_id: 'user5',
      redirect_uris: JSON.stringify(['https://ci.internal.dev/callback']),
      scopes: 'read deploy',
      website: 'https://ci.internal.dev'
    },
    {
      id: 'partner-portal',
      name: 'Partner Portal',
      secret: 'partner-secret-1a2b',
      description: 'External partner integration gateway',
      owner_id: 'user7',
      redirect_uris: JSON.stringify(['https://partners.bigcorp.com/auth/callback']),
      scopes: 'read profile',
      website: 'https://partners.bigcorp.com'
    }
  ];

  const insertClient = db.prepare(`
    INSERT INTO oauth_clients (id, name, secret, description, owner_id, redirect_uris, scopes, website, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
  `);

  for (const c of clients) {
    try {
      insertClient.run(c.id, c.name, c.secret, c.description, c.owner_id, c.redirect_uris, c.scopes, c.website);
    } catch (e) {
      logger.warn(`Could not insert client ${c.id}: ${e.message}`);
    }
  }

  // Seed audit log entries
  const auditEntries = [
    { user_id: 'user1', action: 'user.login', resource_type: 'session', details: 'Admin login from corporate network' },
    { user_id: 'user2', action: 'oauth.authorize', resource_type: 'oauth_client', resource_id: 'dashboard', details: 'Authorized analytics dashboard' },
    { user_id: 'user3', action: 'user.login', resource_type: 'session', details: 'Developer login' },
    { user_id: 'user1', action: 'client.created', resource_type: 'oauth_client', resource_id: 'partner-portal', details: 'Created partner portal client' },
    { user_id: 'user4', action: 'oauth.authorize', resource_type: 'oauth_client', resource_id: 'mobile-app', details: 'Authorized mobile application' },
    { user_id: 'user2', action: 'token.revoked', resource_type: 'access_token', details: 'Manual token revocation' },
    { user_id: 'user5', action: 'user.profile_update', resource_type: 'user', resource_id: 'user5', details: 'Updated bio and contact info' },
    { user_id: 'user1', action: 'admin.user_view', resource_type: 'user', resource_id: 'user3', details: 'Admin reviewed user account' },
  ];

  const insertAudit = db.prepare(`
    INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, created_at)
    VALUES (?, ?, ?, ?, ?, strftime('%s', 'now') - ?)
  `);

  for (let i = 0; i < auditEntries.length; i++) {
    const e = auditEntries[i];
    try {
      insertAudit.run(e.user_id, e.action, e.resource_type || null, e.resource_id || null, e.details, i * 3600);
    } catch (err) {
      logger.warn(`Could not insert audit entry: ${err.message}`);
    }
  }

  logger.info(`Seeded ${users.length} users, ${clients.length} OAuth clients, ${auditEntries.length} audit entries`);
}

module.exports = { seedDatabase };