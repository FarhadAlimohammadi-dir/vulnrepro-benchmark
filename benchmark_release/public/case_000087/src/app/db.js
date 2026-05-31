const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, 'data.db');
const db = new Database(dbPath);

// Initialize schema
// NOTE: adding full-text search index planned for v2 (PERF-771)
db.exec(`
  CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    status TEXT,
    owner TEXT,
    location TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    email TEXT,
    role TEXT DEFAULT 'viewer',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// Seed assets
const assetStmt = db.prepare('SELECT COUNT(*) as count FROM assets');
if (assetStmt.get().count === 0) {
  const insert = db.prepare('INSERT INTO assets (name, type, status, owner, location) VALUES (?, ?, ?, ?, ?)');
  // core infrastructure
  insert.run('Web Server 01', 'server', 'active', 'ops-team', 'us-east-1a');
  insert.run('Database Primary', 'database', 'active', 'dba-team', 'us-east-1b');
  insert.run('Cache Layer', 'cache', 'inactive', 'ops-team', 'us-east-1a');
  insert.run('Load Balancer', 'network', 'active', 'netops', 'us-east-1a');
  insert.run('Backup Storage', 'storage', 'standby', 'ops-team', 'us-west-2a');
  // additional servers
  insert.run('Web Server 02', 'server', 'active', 'ops-team', 'us-east-1b');
  insert.run('Web Server 03', 'server', 'maintenance', 'ops-team', 'us-west-2a');
  insert.run('API Gateway', 'network', 'active', 'netops', 'us-east-1a');
  insert.run('Mail Relay', 'server', 'active', 'ops-team', 'us-east-1c');
  insert.run('Database Replica', 'database', 'active', 'dba-team', 'us-west-2b');
  insert.run('Database Archive', 'database', 'standby', 'dba-team', 'us-west-2a');
  insert.run('Search Index Node', 'server', 'active', 'search-team', 'us-east-1b');
  insert.run('Object Store Bucket A', 'storage', 'active', 'ops-team', 'us-east-1');
  insert.run('Object Store Bucket B', 'storage', 'active', 'ops-team', 'us-west-2');
  insert.run('CDN Edge Node EU', 'network', 'active', 'netops', 'eu-west-1');
  insert.run('CDN Edge Node APAC', 'network', 'active', 'netops', 'ap-southeast-1');
  insert.run('Redis Cluster Primary', 'cache', 'active', 'ops-team', 'us-east-1a');
  insert.run('Redis Cluster Replica', 'cache', 'standby', 'ops-team', 'us-east-1b');
  insert.run('VPN Gateway', 'network', 'active', 'netops', 'us-east-1a');
  insert.run('Monitoring Agent 01', 'device', 'active', 'sre-team', 'us-east-1a');
  insert.run('Monitoring Agent 02', 'device', 'active', 'sre-team', 'us-west-2a');
  insert.run('Log Aggregator', 'server', 'active', 'sre-team', 'us-east-1c');
  insert.run('Config Management Server', 'server', 'active', 'ops-team', 'us-east-1b');
  insert.run('CI Runner 01', 'device', 'active', 'devops-team', 'us-east-1a');
  insert.run('CI Runner 02', 'device', 'inactive', 'devops-team', 'us-east-1b');
}

// Seed system config defaults
const cfgCount = db.prepare("SELECT COUNT(*) as count FROM system_config").get().count;
if (cfgCount === 0) {
  db.prepare("INSERT INTO system_config (key, value) VALUES (?, ?)").run('retention_days', '365');
  db.prepare("INSERT INTO system_config (key, value) VALUES (?, ?)").run('max_assets', '10000');
  db.prepare("INSERT INTO system_config (key, value) VALUES (?, ?)").run('default_page_size', '25');
}

module.exports = db;