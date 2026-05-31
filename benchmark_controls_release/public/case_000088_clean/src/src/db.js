'use strict';

const Database = require('better-sqlite3');
const bcrypt   = require('bcrypt');
const path     = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../data/portal.db');

let _db;

function getDb() {
  if (!_db) {
    _db = new Database(DB_PATH);
    _db.pragma('journal_mode = WAL');
  }
  return _db;
}

function init() {
  const db = getDb();

  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id        INTEGER PRIMARY KEY AUTOINCREMENT,
      username  TEXT UNIQUE NOT NULL,
      email     TEXT UNIQUE NOT NULL,
      password  TEXT NOT NULL,
      role      TEXT NOT NULL DEFAULT 'developer',
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS repositories (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      name        TEXT UNIQUE NOT NULL,
      owner_id    INTEGER NOT NULL,
      description TEXT,
      language    TEXT,
      visibility  TEXT NOT NULL DEFAULT 'private',
      has_config  INTEGER NOT NULL DEFAULT 0,
      remote_url  TEXT,
      created_at  TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id    INTEGER,
      action     TEXT NOT NULL,
      resource   TEXT,
      ip_address TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS webhooks (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      repo_id     INTEGER NOT NULL,
      url         TEXT NOT NULL,
      secret      TEXT NOT NULL,
      events      TEXT NOT NULL DEFAULT 'push',
      active      INTEGER NOT NULL DEFAULT 1,
      created_at  TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY(repo_id) REFERENCES repositories(id)
    );
  `);

  // Seed users
  const existingUser = db.prepare('SELECT id FROM users WHERE username = ?').get('alice');
  if (!existingUser) {
    const users = [
      { username: 'alice',   email: 'alice@devportal.io',   password: 'AlicePass123!',   role: 'admin'     },
      { username: 'bob',     email: 'bob@devportal.io',     password: 'BobPass123!',     role: 'developer' },
      { username: 'charlie', email: 'charlie@devportal.io', password: 'CharliePass123!', role: 'developer' },
      { username: 'diana',   email: 'diana@devportal.io',   password: 'DianaPass123!',   role: 'developer' },
      { username: 'evan',    email: 'evan@devportal.io',    password: 'EvanPass123!',    role: 'developer' },
    ];

    const insertUser = db.prepare(`
      INSERT INTO users (username, email, password, role)
      VALUES (@username, @email, @password, @role)
    `);

    for (const u of users) {
      const hash = bcrypt.hashSync(u.password, 10);
      insertUser.run({ ...u, password: hash });
    }

    // Seed repositories
    const insertRepo = db.prepare(`
      INSERT INTO repositories (name, owner_id, description, language, visibility, has_config, remote_url)
      VALUES (@name, @owner_id, @description, @language, @visibility, @has_config, @remote_url)
    `);

    const repos = [
      { name: 'platform-api',       owner_id: 1, description: 'Core platform REST API',      language: 'Go',         visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/platform-api.git'       },
      { name: 'frontend-app',       owner_id: 1, description: 'React SPA frontend',          language: 'TypeScript', visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/frontend-app.git'       },
      { name: 'data-pipeline',      owner_id: 2, description: 'ETL data pipeline service',   language: 'Python',     visibility: 'private', has_config: 0, remote_url: 'https://github.com/org/data-pipeline.git'      },
      { name: 'auth-service',       owner_id: 2, description: 'OAuth2 / OIDC auth service',  language: 'Java',       visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/auth-service.git'       },
      { name: 'notification-svc',   owner_id: 3, description: 'Push & email notifications',  language: 'Node.js',    visibility: 'private', has_config: 0, remote_url: 'https://github.com/org/notification-svc.git'   },
      { name: 'billing-service',    owner_id: 3, description: 'Stripe billing integration',  language: 'Ruby',       visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/billing-service.git'    },
      { name: 'search-indexer',     owner_id: 4, description: 'Elasticsearch indexing job',  language: 'Python',     visibility: 'internal',has_config: 0, remote_url: 'https://github.com/org/search-indexer.git'     },
      { name: 'infra-terraform',    owner_id: 1, description: 'Terraform IaC modules',       language: 'HCL',        visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/infra-terraform.git'    },
      { name: 'mobile-ios',         owner_id: 4, description: 'iOS Swift application',       language: 'Swift',      visibility: 'private', has_config: 0, remote_url: 'https://github.com/org/mobile-ios.git'         },
      { name: 'mobile-android',     owner_id: 5, description: 'Android Kotlin application',  language: 'Kotlin',     visibility: 'private', has_config: 0, remote_url: 'https://github.com/org/mobile-android.git'     },
      { name: 'docs-site',          owner_id: 5, description: 'Developer documentation',     language: 'Markdown',   visibility: 'public',  has_config: 1, remote_url: 'https://github.com/org/docs-site.git'          },
      { name: 'analytics-worker',   owner_id: 2, description: 'Async analytics processor',   language: 'Go',         visibility: 'private', has_config: 0, remote_url: 'https://github.com/org/analytics-worker.git'   },
      { name: 'cache-proxy',        owner_id: 3, description: 'Redis caching proxy layer',   language: 'C++',        visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/cache-proxy.git'        },
      { name: 'ml-training',        owner_id: 4, description: 'ML model training pipeline',  language: 'Python',     visibility: 'internal',has_config: 0, remote_url: 'https://github.com/org/ml-training.git'        },
      { name: 'gateway-service',    owner_id: 1, description: 'API gateway / rate limiter',  language: 'Go',         visibility: 'private', has_config: 1, remote_url: 'https://github.com/org/gateway-service.git'    },
    ];

    for (const r of repos) {
      insertRepo.run(r);
    }

    // Seed audit logs
    const insertLog = db.prepare(`
      INSERT INTO audit_logs (user_id, action, resource, ip_address)
      VALUES (@user_id, @action, @resource, @ip_address)
    `);
    const actions = [
      { user_id: 1, action: 'LOGIN',           resource: null,            ip_address: '10.0.0.1' },
      { user_id: 1, action: 'REPO_REGISTER',   resource: 'platform-api',  ip_address: '10.0.0.1' },
      { user_id: 2, action: 'LOGIN',           resource: null,            ip_address: '10.0.0.5' },
      { user_id: 2, action: 'REPO_CHECK',      resource: 'data-pipeline', ip_address: '10.0.0.5' },
      { user_id: 3, action: 'WEBHOOK_CREATE',  resource: 'billing-service',ip_address: '10.0.0.9'},
      { user_id: 1, action: 'USER_UPDATE',     resource: 'alice',         ip_address: '10.0.0.1' },
      { user_id: 4, action: 'LOGIN',           resource: null,            ip_address: '10.0.1.3' },
      { user_id: 5, action: 'REPO_REGISTER',   resource: 'mobile-android',ip_address: '10.0.1.7' },
    ];
    for (const l of actions) { insertLog.run(l); }
  }

  console.log('[db] Schema ready');
}

module.exports = { getDb, init };