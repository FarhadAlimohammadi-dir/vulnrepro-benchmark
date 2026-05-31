'use strict';

const db = require('../models/database');
const crypto = require('crypto');

function seedDatabase() {
  try {
    db.initialize();
  } catch (e) {
    // Already initialized
  }

  const users = [
    { id: 'admin1', email: 'admin@nexus.io', password: 'Admin@2024!', display_name: 'Nexus Admin', role: 'admin' },
    { id: 'user1', email: 'alice@example.com', password: 'pass123', display_name: 'Alice Chen', role: 'user' },
    { id: 'user2', email: 'bob@example.com', password: 'pass456', display_name: 'Bob Martinez', role: 'user' },
    { id: 'victim', email: 'victim@example.com', password: 'victimpass', display_name: 'Victor Kim', role: 'user' },
    { id: 'user4', email: 'diana@example.com', password: 'diana2024', display_name: 'Diana Patel', role: 'user' },
    { id: 'user5', email: 'evan@example.com', password: 'evan2024', display_name: 'Evan Nguyen', role: 'user' },
    { id: 'user6', email: 'fiona@example.com', password: 'fiona2024', display_name: 'Fiona Walsh', role: 'user' },
    { id: 'user7', email: 'george@example.com', password: 'george2024', display_name: 'George Okonkwo', role: 'user' },
    { id: 'user8', email: 'helen@example.com', password: 'helen2024', display_name: 'Helen Rousseau', role: 'user' },
    { id: 'user9', email: 'ivan@example.com', password: 'ivan2024', display_name: 'Ivan Sorokin', role: 'user' },
    { id: 'user10', email: 'julia@example.com', password: 'julia2024', display_name: 'Julia Ferreira', role: 'user' },
    { id: 'user11', email: 'kevin@example.com', password: 'kevin2024', display_name: 'Kevin Larsson', role: 'user' },
    { id: 'user12', email: 'laura@example.com', password: 'laura2024', display_name: 'Laura Hoffmann', role: 'user' },
  ];

  for (const u of users) {
    try {
      db.addUser(u);
    } catch (e) {
      // Already seeded
    }
  }

  const clients = [
    {
      id: 'shop-app',
      name: 'Nexus Shop',
      client_secret: crypto.randomBytes(32).toString('hex'),
      redirect_uris: 'https://shop.example.com/callback',
      scopes: 'openid profile email orders',
      owner_id: 'admin1'
    },
    {
      id: 'analytics-app',
      name: 'Analytics Dashboard',
      client_secret: crypto.randomBytes(32).toString('hex'),
      redirect_uris: 'https://analytics.example.com/callback',
      scopes: 'openid profile email',
      owner_id: 'admin1'
    },
    {
      id: 'mobile-app',
      name: 'Nexus Mobile',
      client_secret: crypto.randomBytes(32).toString('hex'),
      redirect_uris: 'https://app.example.com/callback',
      scopes: 'openid profile email notifications',
      owner_id: 'admin1'
    },
    {
      id: 'devtools',
      name: 'Developer Tools',
      client_secret: crypto.randomBytes(32).toString('hex'),
      redirect_uris: 'http://localhost:3000/callback',
      scopes: 'openid profile email api:read api:write',
      owner_id: 'user1'
    }
  ];

  for (const c of clients) {
    try {
      db.addOAuthClient(c);
    } catch (e) {
      // Already seeded
    }
  }

  const orgs = [
    { id: 'org1', name: 'Acme Corp', slug: 'acme', owner_id: 'user1', plan: 'business' },
    { id: 'org2', name: 'Globex Industries', slug: 'globex', owner_id: 'user2', plan: 'enterprise' },
    { id: 'org3', name: 'Initech Solutions', slug: 'initech', owner_id: 'user4', plan: 'free' },
    { id: 'org4', name: 'Umbrella Technologies', slug: 'umbrella', owner_id: 'admin1', plan: 'business' },
  ];

  for (const o of orgs) {
    try {
      db.addOrganization(o);
    } catch (e) {
      // Already seeded
    }
  }
}

// Allow direct execution
if (require.main === module) {
  seedDatabase();
  console.log('[seed] Database seeded successfully.');
  process.exit(0);
}

module.exports = { seedDatabase };