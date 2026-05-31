'use strict';

const { v4: uuidv4 } = require('uuid');

function seedDatabase(db) {
  const count = db.prepare('SELECT COUNT(*) as c FROM users').get();
  if (count.c > 0) return;

  console.log('[SEED] Seeding database with initial data...');

  const now = Date.now();

  // Users
  const users = [
    { id: 'user1', username: 'alice', password: 'pass123', email: 'alice@example.com', instagram_id: 'ig_alice_001', role: 'admin', bio: 'Product manager and pixel enthusiast', website: 'https://alice.dev' },
    { id: 'user2', username: 'bob', password: 'pass456', email: 'bob@example.com', instagram_id: 'ig_bob_002', role: 'user', bio: 'Frontend developer', website: 'https://bob.io' },
    { id: 'user3', username: 'charlie', password: 'pass789', email: 'charlie@example.com', instagram_id: 'ig_charlie_003', role: 'user', bio: 'Growth hacker', website: null },
    { id: 'user4', username: 'diana', password: 'dpass101', email: 'diana@example.com', instagram_id: 'ig_diana_004', role: 'user', bio: 'Data analyst', website: 'https://diana.analytics' },
    { id: 'user5', username: 'evan', password: 'epass202', email: 'evan@example.com', instagram_id: 'ig_evan_005', role: 'user', bio: 'Marketing specialist', website: null },
    { id: 'user6', username: 'fiona', password: 'fpass303', email: 'fiona@example.com', instagram_id: 'ig_fiona_006', role: 'developer', bio: 'API integration expert', website: 'https://fiona.codes' },
  ];

  const insertUser = db.prepare(`
    INSERT INTO users (id, username, password, email, instagram_id, role, created_at, bio, website)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  for (const u of users) {
    insertUser.run(u.id, u.username, u.password, u.email, u.instagram_id, u.role, now - Math.floor(Math.random() * 30) * 86400000, u.bio, u.website);
  }

  // Apps
  const apps = [
    { id: 'test_app_123', name: 'Test Application', owner_id: 'user1', redirect_uri: 'http://localhost:9000', scopes: 'user_profile,email', pixel_id: 'px_001', secret: 'app_secret_aaa', description: 'Primary test application for OAuth flows' },
    { id: 'app_ecommerce_001', name: 'ShopTrack Pro', owner_id: 'user2', redirect_uri: 'https://shop.example.com/callback', scopes: 'user_profile,purchases', pixel_id: 'px_002', secret: 'app_secret_bbb', description: 'E-commerce conversion tracking' },
    { id: 'app_blog_002', name: 'ContentMetrics', owner_id: 'user3', redirect_uri: 'https://blog.example.com/auth', scopes: 'user_profile', pixel_id: 'px_003', secret: 'app_secret_ccc', description: 'Blog engagement analytics' },
    { id: 'app_media_003', name: 'MediaPulse', owner_id: 'user6', redirect_uri: 'https://media.example.com/oauth', scopes: 'user_profile,media', pixel_id: 'px_004', secret: 'app_secret_ddd', description: 'Social media performance tracker' },
    { id: 'app_crm_004', name: 'LeadFlow CRM', owner_id: 'user4', redirect_uri: 'https://crm.example.com/connect', scopes: 'user_profile,leads', pixel_id: 'px_005', secret: 'app_secret_eee', description: 'CRM lead attribution system' },
  ];

  const insertApp = db.prepare(`
    INSERT INTO apps (id, name, owner_id, redirect_uri, scopes, pixel_id, secret, created_at, description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  for (const a of apps) {
    insertApp.run(a.id, a.name, a.owner_id, a.redirect_uri, a.scopes, a.pixel_id, a.secret, now - Math.floor(Math.random() * 60) * 86400000, a.description);
  }

  // Pixel events
  const eventTypes = ['PageView', 'AddToCart', 'Purchase', 'Lead', 'CompleteRegistration', 'ViewContent', 'Search'];
  const insertEvent = db.prepare(`
    INSERT INTO pixel_events (id, pixel_id, event_type, page_url, referrer, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  for (let i = 0; i < 25; i++) {
    insertEvent.run(
      uuidv4(),
      apps[i % apps.length].pixel_id,
      eventTypes[i % eventTypes.length],
      `https://example.com/page${i}`,
      i % 3 === 0 ? 'https://google.com' : null,
      now - i * 3600000
    );
  }

  // Audit log entries
  const insertAudit = db.prepare(`
    INSERT INTO audit_log (id, actor_id, action, resource_type, resource_id, details, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  const auditEntries = [
    { actor: 'user1', action: 'CREATE_APP', rt: 'app', rid: 'test_app_123', details: 'Created application Test Application' },
    { actor: 'user2', action: 'CREATE_APP', rt: 'app', rid: 'app_ecommerce_001', details: 'Created application ShopTrack Pro' },
    { actor: 'user1', action: 'LOGIN', rt: 'session', rid: null, details: 'Successful login from 127.0.0.1' },
    { actor: 'user3', action: 'UPDATE_PROFILE', rt: 'user', rid: 'user3', details: 'Profile bio updated' },
    { actor: 'user6', action: 'CREATE_APP', rt: 'app', rid: 'app_media_003', details: 'Created application MediaPulse' },
    { actor: 'user1', action: 'REVOKE_TOKEN', rt: 'token', rid: 'tok_old_001', details: 'Token revoked by owner' },
    { actor: 'user4', action: 'LOGIN', rt: 'session', rid: null, details: 'Successful login from 10.0.0.5' },
  ];

  for (const e of auditEntries) {
    insertAudit.run(uuidv4(), e.actor, e.action, e.rt, e.rid, e.details, now - Math.floor(Math.random() * 7) * 86400000);
  }

  console.log('[SEED] Database seeded successfully');
}

module.exports = { seedDatabase };