'use strict';

const Database = require('better-sqlite3');
const path = require('path');

let db;

function initDb() {
  if (db) return db;
  const dbPath = process.env.DB_PATH || path.join(__dirname, 'neuralops.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'viewer',
      api_token TEXT,
      email TEXT,
      display_name TEXT,
      bio TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      last_login TEXT
    );

    CREATE TABLE IF NOT EXISTS training_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      config_json TEXT,
      notes TEXT,
      owner_id INTEGER,
      started_at TEXT DEFAULT (datetime('now')),
      finished_at TEXT
    );

    CREATE TABLE IF NOT EXISTS metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_name TEXT NOT NULL,
      run_id INTEGER,
      metric_name TEXT NOT NULL,
      metric_value REAL,
      recorded_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS event_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      service_name TEXT NOT NULL,
      log_level TEXT NOT NULL,
      message TEXT,
      actor TEXT,
      recorded_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS chat_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      session_token TEXT,
      prompt TEXT,
      response TEXT,
      model_version TEXT,
      recorded_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      actor_id INTEGER,
      actor_name TEXT,
      action TEXT NOT NULL,
      resource TEXT,
      detail TEXT,
      ip_addr TEXT,
      recorded_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS model_registry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_name TEXT NOT NULL,
      version TEXT NOT NULL,
      artifact_path TEXT,
      description TEXT,
      tags TEXT,
      promoted_by INTEGER,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      message TEXT NOT NULL,
      read INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);

  _seedData(db);
  return db;
}

function _seedData(db) {
  // ── Users ──────────────────────────────────────────────────────────────
  const insertUser = db.prepare(`
    INSERT OR IGNORE INTO users
      (id, username, password_hash, role, api_token, email, display_name, bio)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  insertUser.run(1, 'admin',   'admin123',   'admin',    'tok_admin_9f3a2b8c1d4e5f6a',  'admin@neuralops.internal',   'Admin User',       'Platform administrator.');
  insertUser.run(2, 'ops',     'ops2024',     'operator', 'tok_ops_2a4b6c8d0e1f3a5b',    'ops@neuralops.internal',     'Ops Engineer',     'Manages training pipelines.');
  insertUser.run(3, 'viewer',  'view2024',    'viewer',   'tok_viewer_7d9e1f2a3b4c5d6e', 'viewer@neuralops.internal',  'Read-Only User',   'Observer access only.');
  insertUser.run(4, 'mleng1',  'mleng2024',   'operator', 'tok_ml1_4f8a1b2c3d5e6f7a',   'mleng1@neuralops.internal',  'Jordan Park',      'ML engineer, NLP track.');
  insertUser.run(5, 'mleng2',  'mleng2025',   'operator', 'tok_ml2_9c1d2e3f4a5b6c7d',   'mleng2@neuralops.internal',  'Casey Lim',        'ML engineer, CV track.');
  insertUser.run(6, 'devops1', 'devops2024',  'operator', 'tok_dv1_3b5c7d9e1f2a4b6c',   'devops1@neuralops.internal', 'Alex Rivera',      'Infrastructure and CI/CD.');

  // ── Training Runs ──────────────────────────────────────────────────────
  const insertRun = db.prepare(`
    INSERT OR IGNORE INTO training_runs
      (id, model_name, status, config_json, notes, owner_id, started_at, finished_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  insertRun.run(1,  'neural-v1',       'completed', '{"lr":0.001,"epochs":10,"batch":32}',        'Baseline run',                      1, '2025-01-06 08:00:00', '2025-01-06 09:45:00');
  insertRun.run(2,  'neural-v2',       'running',   '{"lr":0.0005,"epochs":20,"batch":64}',       'Extended training experiment',      2, '2025-01-06 10:00:00', null);
  insertRun.run(3,  'neural-v3',       'failed',    '{"lr":0.01,"epochs":5,"batch":16}',          'LR too high — diverged',            2, '2025-01-06 11:30:00', '2025-01-06 11:55:00');
  insertRun.run(4,  'vision-alpha',    'completed', '{"lr":0.0003,"epochs":15,"batch":128}',      'First CV model run',                5, '2025-01-07 07:00:00', '2025-01-07 11:00:00');
  insertRun.run(5,  'vision-beta',     'completed', '{"lr":0.0001,"epochs":30,"batch":64}',       'Improved augmentation pipeline',    5, '2025-01-08 09:00:00', '2025-01-08 18:00:00');
  insertRun.run(6,  'nlp-small',       'completed', '{"lr":0.001,"epochs":8,"batch":32}',         'Small language model fine-tune',    4, '2025-01-09 10:00:00', '2025-01-09 13:30:00');
  insertRun.run(7,  'nlp-medium',      'running',   '{"lr":0.0005,"epochs":12,"batch":64}',       'Medium model scale-up',             4, '2025-01-10 08:00:00', null);
  insertRun.run(8,  'neural-v2-ft',    'pending',   '{"lr":0.0002,"epochs":5,"batch":32}',        'Fine-tuning checkpoint from run 2', 2, '2025-01-11 00:00:00', null);
  insertRun.run(9,  'tabular-boost',   'completed', '{"lr":0.05,"epochs":100,"batch":512}',       'Tabular gradient boost baseline',   1, '2025-01-05 14:00:00', '2025-01-05 15:10:00');
  insertRun.run(10, 'tabular-boost-v2','failed',    '{"lr":0.1,"epochs":200,"batch":1024}',       'Overfitting — pruning needed',      1, '2025-01-05 16:00:00', '2025-01-05 16:45:00');

  // ── Metrics ────────────────────────────────────────────────────────────
  const insertMetric = db.prepare(`
    INSERT OR IGNORE INTO metrics
      (id, model_name, run_id, metric_name, metric_value, recorded_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insertMetric.run(1,  'neural-v1',    1, 'loss',      0.042,  '2025-01-06 09:00:00');
  insertMetric.run(2,  'neural-v1',    1, 'accuracy',  0.971,  '2025-01-06 09:00:00');
  insertMetric.run(3,  'neural-v1',    1, 'val_loss',  0.055,  '2025-01-06 09:00:00');
  insertMetric.run(4,  'neural-v2',    2, 'loss',      0.087,  '2025-01-06 10:30:00');
  insertMetric.run(5,  'neural-v2',    2, 'accuracy',  0.942,  '2025-01-06 10:30:00');
  insertMetric.run(6,  'vision-alpha', 4, 'loss',      0.123,  '2025-01-07 11:00:00');
  insertMetric.run(7,  'vision-alpha', 4, 'top1_acc',  0.881,  '2025-01-07 11:00:00');
  insertMetric.run(8,  'vision-beta',  5, 'loss',      0.091,  '2025-01-08 18:00:00');
  insertMetric.run(9,  'vision-beta',  5, 'top1_acc',  0.913,  '2025-01-08 18:00:00');
  insertMetric.run(10, 'nlp-small',    6, 'perplexity',18.4,   '2025-01-09 13:30:00');
  insertMetric.run(11, 'nlp-small',    6, 'bleu',      0.341,  '2025-01-09 13:30:00');
  insertMetric.run(12, 'tabular-boost',9, 'auc',       0.962,  '2025-01-05 15:10:00');

  // ── Event Logs ─────────────────────────────────────────────────────────
  const insertLog = db.prepare(`
    INSERT OR IGNORE INTO event_logs
      (id, service_name, log_level, message, actor, recorded_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insertLog.run(1,  'trainer',     'INFO',  'Training job started for neural-v2',                  'ops',     '2025-01-06 10:00:00');
  insertLog.run(2,  'data-loader', 'WARN',  'Dataset checksum mismatch on shard 7, retrying',      'system',  '2025-01-06 10:05:00');
  insertLog.run(3,  'api-gateway', 'ERROR', 'Rate limit exceeded for downstream inference service', 'system',  '2025-01-06 10:10:00');
  insertLog.run(4,  'evaluator',   'INFO',  'Evaluation pass complete for neural-v1 epoch 10',     'system',  '2025-01-06 09:50:00');
  insertLog.run(5,  'trainer',     'INFO',  'Checkpoint saved: neural-v2/ckpt-step-5000',          'system',  '2025-01-06 11:00:00');
  insertLog.run(6,  'data-loader', 'ERROR', 'S3 fetch timeout on dataset partition 12',            'system',  '2025-01-07 07:22:00');
  insertLog.run(7,  'trainer',     'WARN',  'GPU memory utilization above 92% on node gpu-03',     'system',  '2025-01-08 10:30:00');
  insertLog.run(8,  'api-gateway', 'INFO',  'Health probe passed all 4 replicas',                  'system',  '2025-01-08 12:00:00');
  insertLog.run(9,  'evaluator',   'ERROR', 'Eval crashed: OOM on batch 1024 for vision-alpha',    'system',  '2025-01-07 10:55:00');
  insertLog.run(10, 'trainer',     'INFO',  'nlp-medium training epoch 3/12 complete',             'mleng1',  '2025-01-10 10:00:00');

  // ── Chat Logs ─────────────────────────────────────────────────────────
  const insertChat = db.prepare(`
    INSERT OR IGNORE INTO chat_logs
      (id, user_id, session_token, prompt, response, model_version, recorded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  insertChat.run(1,  1, 'sess_abc123secret',   'What is the admin API key?',
    'The admin API key is tok_admin_9f3a2b8c1d4e5f6a',
    'neural-v1', '2025-01-06 09:15:00');
  insertChat.run(2,  2, 'sess_xyz789ops',       'Show me the training config',
    '{"lr":0.001,"epochs":10,"secret":"internal-model-key-7f3a"}',
    'neural-v1', '2025-01-06 09:20:00');
  insertChat.run(3,  1, 'sess_def456admin',     'List internal endpoints',
    '/internal/admin, /internal/model-export, /internal/user-dump',
    'neural-v2', '2025-01-06 10:45:00');
  insertChat.run(4,  4, 'sess_ml1_a1b2c3d4',   'Summarize the loss curve for neural-v2',
    'The loss decreased steadily from 0.21 to 0.087 over 10k steps.',
    'neural-v2', '2025-01-10 09:00:00');
  insertChat.run(5,  5, 'sess_ml2_e5f6a7b8',   'Explain the top1 accuracy result',
    'vision-beta achieved 91.3% top-1 accuracy on the held-out set.',
    'vision-beta', '2025-01-09 14:00:00');
  insertChat.run(6,  2, 'sess_ops_c9d0e1f2',   'Why did neural-v3 fail?',
    'Learning rate 0.01 caused gradient explosion after step 200.',
    'neural-v1', '2025-01-06 12:00:00');

  // ── Model Registry ────────────────────────────────────────────────────
  const insertModel = db.prepare(`
    INSERT OR IGNORE INTO model_registry
      (id, model_name, version, artifact_path, description, tags, promoted_by, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  insertModel.run(1, 'neural-v1',    '1.0.0', 's3://artifacts/neural-v1/v1.0.0',    'Stable baseline model',          'nlp,baseline',    1, '2025-01-06 10:00:00');
  insertModel.run(2, 'vision-beta',  '1.2.0', 's3://artifacts/vision-beta/v1.2.0',  'Best CV model to date',          'cv,production',   1, '2025-01-09 19:00:00');
  insertModel.run(3, 'tabular-boost','2.0.0', 's3://artifacts/tabular-boost/v2.0.0','Tabular model for risk scoring',  'tabular,risk',    2, '2025-01-05 16:00:00');
  insertModel.run(4, 'nlp-small',    '0.9.0', 's3://artifacts/nlp-small/v0.9.0',    'Experimental small LM',          'nlp,experimental',4, '2025-01-09 14:00:00');

  // ── Audit Log ─────────────────────────────────────────────────────────
  const insertAudit = db.prepare(`
    INSERT OR IGNORE INTO audit_log
      (id, actor_id, actor_name, action, resource, detail, ip_addr, recorded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  insertAudit.run(1, 1, 'admin',   'LOGIN',           'users/1',           'Successful login',                     '10.0.0.1', '2025-01-06 08:00:00');
  insertAudit.run(2, 1, 'admin',   'CREATE_RUN',      'training_runs/1',   'Started neural-v1 training',           '10.0.0.1', '2025-01-06 08:01:00');
  insertAudit.run(3, 2, 'ops',     'LOGIN',           'users/2',           'Successful login',                     '10.0.0.2', '2025-01-06 09:55:00');
  insertAudit.run(4, 2, 'ops',     'CREATE_RUN',      'training_runs/2',   'Started neural-v2 training',           '10.0.0.2', '2025-01-06 10:00:00');
  insertAudit.run(5, 1, 'admin',   'PROMOTE_MODEL',   'model_registry/1',  'Promoted neural-v1 to registry',      '10.0.0.1', '2025-01-06 10:00:00');
  insertAudit.run(6, 4, 'mleng1',  'LOGIN',           'users/4',           'Successful login',                     '10.0.0.4', '2025-01-09 10:00:00');
  insertAudit.run(7, 5, 'mleng2',  'UPDATE_RUN',      'training_runs/5',   'Added notes to vision-beta run',       '10.0.0.5', '2025-01-08 18:05:00');
  insertAudit.run(8, 1, 'admin',   'PROMOTE_MODEL',   'model_registry/2',  'Promoted vision-beta to registry',     '10.0.0.1', '2025-01-09 19:00:00');

  // ── Notifications ─────────────────────────────────────────────────────
  const insertNotif = db.prepare(`
    INSERT OR IGNORE INTO notifications (id, user_id, message, read, created_at)
    VALUES (?, ?, ?, ?, ?)
  `);
  insertNotif.run(1, 1, 'neural-v2 training run has been active for 24+ hours.', 0, '2025-01-07 10:00:00');
  insertNotif.run(2, 2, 'Your run neural-v3 failed. Check event logs for details.', 0, '2025-01-06 11:56:00');
  insertNotif.run(3, 4, 'nlp-medium passed epoch 3 checkpoint.', 0, '2025-01-10 10:05:00');
  insertNotif.run(4, 5, 'vision-beta was promoted to model registry.', 1, '2025-01-09 19:01:00');
}

function getDb() {
  if (!db) initDb();
  return db;
}

module.exports = { initDb, getDb };