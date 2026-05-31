const Database = require('better-sqlite3');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

class DatabaseManager {
  constructor() {
    this.db = null;
    this.dbPath = path.join(__dirname, '../data.db');
  }

  initialize() {
    this.db = new Database(this.dbPath);
    this.createTables();
    this.seedInitialData();
  }

  createTables() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_login DATETIME
      );

      CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        webhook_url TEXT NOT NULL,
        headers TEXT,
        method TEXT DEFAULT 'POST',
        enabled INTEGER DEFAULT 1,
        execution_count INTEGER DEFAULT 0,
        last_executed DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      );

      CREATE TABLE IF NOT EXISTS workflow_executions (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        status_code INTEGER,
        response_body TEXT,
        error_message TEXT,
        execution_time_ms INTEGER,
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
      );

      CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        action TEXT NOT NULL,
        description TEXT,
        ip_address TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      );

      CREATE TABLE IF NOT EXISTS integrations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        integration_type TEXT NOT NULL,
        provider_name TEXT,
        config TEXT,
        enabled INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      );
    `);
  }

  seedInitialData() {
    const userStmt = this.db.prepare('SELECT COUNT(*) as count FROM users');
    const result = userStmt.get();

    if (result.count === 0) {
      const users = [
        { id: uuidv4(), username: 'alice', password: 'alice', email: 'alice@example.com', role: 'user' },
        { id: uuidv4(), username: 'bob', password: 'bob', email: 'bob@example.com', role: 'user' },
        { id: uuidv4(), username: 'charlie', password: 'admin-demo-only', email: 'charlie@example.com', role: 'admin' },
        { id: uuidv4(), username: 'diana', password: 'diana', email: 'diana@example.com', role: 'user' },
        { id: uuidv4(), username: 'eve', password: 'eve', email: 'eve@example.com', role: 'user' }
      ];

      const insertUser = this.db.prepare(
        'INSERT INTO users (id, username, password, email, role) VALUES (?, ?, ?, ?, ?)'
      );

      for (const user of users) {
        try {
          insertUser.run(user.id, user.username, user.password, user.email, user.role);
        } catch (e) {
          // User already exists
        }
      }

      // Seed sample workflows
      const aliceId = users[0].id;
      const workflows = [
        {
          id: uuidv4(),
          user_id: aliceId,
          name: 'Daily Report Export',
          description: 'Export daily metrics to analytics platform',
          webhook_url: 'https://analytics.example.com/v1/import',
          headers: JSON.stringify({ 'Authorization': 'Bearer token123' }),
          method: 'POST',
          execution_count: 5
        },
        {
          id: uuidv4(),
          user_id: aliceId,
          name: 'Slack Team Alert',
          description: 'Send alert to engineering team on Slack',
          webhook_url: 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX',
          headers: JSON.stringify({ 'Content-Type': 'application/json' }),
          method: 'POST',
          execution_count: 12
        },
        {
          id: uuidv4(),
          user_id: aliceId,
          name: 'Data Sync to S3',
          description: 'Archive processed data to S3 bucket',
          webhook_url: 'https://aws-endpoint.example.com/sync',
          headers: JSON.stringify({ 'X-API-Key': 'secret123' }),
          method: 'PUT',
          execution_count: 0
        }
      ];

      const insertWorkflow = this.db.prepare(
        'INSERT INTO workflows (id, user_id, name, description, webhook_url, headers, method, execution_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
      );

      for (const workflow of workflows) {
        try {
          insertWorkflow.run(
            workflow.id,
            workflow.user_id,
            workflow.name,
            workflow.description,
            workflow.webhook_url,
            workflow.headers,
            workflow.method,
            workflow.execution_count
          );
        } catch (e) {
          // Workflow already exists
        }
      }
    }
  }

  getDb() {
    return this.db;
  }

  close() {
    if (this.db) {
      this.db.close();
    }
  }
}

module.exports = DatabaseManager;
