const Database = require('better-sqlite3');
const path = require('path');
const crypto = require('crypto');

const db = new Database(path.join(__dirname, 'filevault.db'));

function initializeDatabase() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS files (
      file_id TEXT PRIMARY KEY,
      owner_id TEXT NOT NULL,
      filename TEXT NOT NULL,
      content TEXT NOT NULL,
      size INTEGER NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      log_id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,
      file_id TEXT,
      action TEXT NOT NULL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_preferences (
      user_id TEXT PRIMARY KEY,
      theme TEXT DEFAULT 'light',
      notifications TEXT DEFAULT 'on',
      default_sort TEXT DEFAULT 'name'
    );
  `);

  // Seed data for demo users
  const seedStmt = db.prepare('SELECT COUNT(*) as cnt FROM files');
  const result = seedStmt.get();

  if (result.cnt === 0) {
    const insertFile = db.prepare(
      'INSERT INTO files (file_id, owner_id, filename, content, size) VALUES (?, ?, ?, ?, ?)'
    );

    // Alice's files — project documents
    const aliceFiles = [
      ['project_0.txt', 'Confidential project plan 0 - Alice\'s document'],
      ['project_1.txt', 'Confidential project plan 1 - Alice\'s document'],
      ['project_2.txt', 'Confidential project plan 2 - Alice\'s document'],
      ['project_3.txt', 'Confidential project plan 3 - Alice\'s document'],
      ['project_4.txt', 'Confidential project plan 4 - Alice\'s document'],
      ['roadmap_2024.txt', 'Confidential product roadmap - Alice\'s document'],
      ['meeting_notes.txt', 'Confidential meeting notes from Q4 planning session'],
      ['budget_draft.txt', 'Confidential draft budget for next fiscal year']
    ];
    for (const [fname, content] of aliceFiles) {
      insertFile.run(crypto.randomUUID(), 'user_alice', fname, content, content.length);
    }

    // Bob's files — financial reports
    const bobFiles = [
      ['report_0.txt', 'Private financial report 0 - Bob\'s data'],
      ['report_1.txt', 'Private financial report 1 - Bob\'s data'],
      ['report_2.txt', 'Private financial report 2 - Bob\'s data'],
      ['report_3.txt', 'Private financial report 3 - Bob\'s data'],
      ['report_4.txt', 'Private financial report 4 - Bob\'s data'],
      ['q1_summary.txt', 'Private Q1 Financial Summary - Bob\'s analysis'],
      ['expenses_march.txt', 'Private expense ledger March - Bob\'s data'],
    ];
    for (const [fname, content] of bobFiles) {
      insertFile.run(crypto.randomUUID(), 'user_bob', fname, content, content.length);
    }

    // Admin files — system configuration
    for (let i = 0; i < 3; i++) {
      const content = `System configuration file ${i}`;
      insertFile.run(crypto.randomUUID(), 'user_admin', `config_${i}.txt`, content, content.length);
    }

    // Carol's files
    const carolFiles = [
      ['design_spec.txt', 'UI design specification draft v2'],
      ['component_list.txt', 'Reusable component library catalog'],
      ['style_guide.txt', 'Brand style guide and typography rules']
    ];
    for (const [fname, content] of carolFiles) {
      insertFile.run(crypto.randomUUID(), 'user_carol', fname, content, content.length);
    }

    // Dave's files
    const daveFiles = [
      ['infra_notes.txt', 'Infrastructure migration notes — do not share'],
      ['oncall_runbook.txt', 'On-call runbook for prod incidents'],
      ['capacity_plan.txt', 'Capacity planning worksheet Q2']
    ];
    for (const [fname, content] of daveFiles) {
      insertFile.run(crypto.randomUUID(), 'user_dave', fname, content, content.length);
    }

    // Seed some audit log entries
    // TODO: emit these via structured logging pipeline in prod
    const insertLog = db.prepare(
      'INSERT INTO audit_logs (user_id, file_id, action) VALUES (?, ?, ?)'
    );
    insertLog.run('user_alice', null, 'login');
    insertLog.run('user_bob', null, 'login');
    insertLog.run('user_admin', null, 'login');
  }
}

function getFile(file_id) {
  const stmt = db.prepare('SELECT * FROM files WHERE file_id = ?');
  return stmt.get(file_id);
}

function listUserFiles(user_id) {
  // NOTE: add ORDER BY clause once index on (owner_id, created_at) is confirmed
  const stmt = db.prepare('SELECT file_id, filename, size, created_at FROM files WHERE owner_id = ?');
  return stmt.all(user_id);
}

function createFile(user_id, filename, content) {
  const file_id = crypto.randomUUID();
  const size = content.length;
  const stmt = db.prepare(
    'INSERT INTO files (file_id, owner_id, filename, content, size) VALUES (?, ?, ?, ?, ?)'
  );
  stmt.run(file_id, user_id, filename, content, size);
  return file_id;
}

function deleteFile(file_id) {
  const stmt = db.prepare('DELETE FROM files WHERE file_id = ?');
  stmt.run(file_id);
}

function getAuditLogs(user_id) {
  const stmt = db.prepare('SELECT * FROM audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50');
  return stmt.all(user_id);
}

function recordAudit(user_id, file_id, action) {
  const stmt = db.prepare('INSERT INTO audit_logs (user_id, file_id, action) VALUES (?, ?, ?)');
  stmt.run(user_id, file_id || null, action);
}

function getPreferences(user_id) {
  const stmt = db.prepare('SELECT * FROM user_preferences WHERE user_id = ?');
  return stmt.get(user_id);
}

function savePreferences(user_id, prefs) {
  const stmt = db.prepare(`
    INSERT INTO user_preferences (user_id, theme, notifications, default_sort)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
      theme = excluded.theme,
      notifications = excluded.notifications,
      default_sort = excluded.default_sort
  `);
  stmt.run(user_id, prefs.theme, prefs.notifications, prefs.defaultSort);
}

function healthCheck() {
  try {
    db.prepare('SELECT 1').get();
    return true;
  } catch (e) {
    return false;
  }
}

module.exports = {
  initializeDatabase,
  getFile,
  listUserFiles,
  createFile,
  deleteFile,
  getAuditLogs,
  recordAudit,
  getPreferences,
  savePreferences,
  healthCheck
};