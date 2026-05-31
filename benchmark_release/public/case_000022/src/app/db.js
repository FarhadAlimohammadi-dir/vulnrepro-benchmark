'use strict';

const Database = require('better-sqlite3');
const crypto   = require('crypto');
const path     = require('path');

let db;

function getDb() { return db; }

function h(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

function initDb() {
  const dbPath = process.env.DB_PATH || path.join(__dirname, 'codepilot.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      username      TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role          TEXT NOT NULL DEFAULT 'dev',
      email         TEXT,
      bio           TEXT,
      avatar_url    TEXT,
      created_at    INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS repos (
      id          TEXT PRIMARY KEY,
      full_name   TEXT UNIQUE NOT NULL,
      description TEXT,
      language    TEXT,
      owner       TEXT,
      private     INTEGER DEFAULT 0,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS issues (
      id          TEXT PRIMARY KEY,
      title       TEXT NOT NULL,
      body        TEXT,
      labels      TEXT DEFAULT '[]',
      repo        TEXT,
      author      TEXT,
      status      TEXT DEFAULT 'open',
      priority    TEXT DEFAULT 'medium',
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000),
      updated_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS tasks (
      id          TEXT PRIMARY KEY,
      issue_id    TEXT,
      triggered_by TEXT,
      plan        TEXT DEFAULT '[]',
      status      TEXT DEFAULT 'pending',
      results     TEXT DEFAULT '[]',
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000),
      finished_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS comments (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      issue_id    TEXT NOT NULL,
      author      TEXT NOT NULL,
      body        TEXT NOT NULL,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      actor       TEXT,
      action      TEXT NOT NULL,
      target_type TEXT,
      target_id   TEXT,
      meta        TEXT,
      created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
    );

    CREATE INDEX IF NOT EXISTS idx_issues_status    ON issues(status);
    CREATE INDEX IF NOT EXISTS idx_issues_repo      ON issues(repo);
    CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_audit_actor      ON audit_log(actor);
    CREATE INDEX IF NOT EXISTS idx_comments_issue   ON comments(issue_id);
  `);

  seedUsers();
  seedRepos();
  seedIssues();
}

function seedUsers() {
  const ins = db.prepare(
    'INSERT OR IGNORE INTO users (username, password_hash, role, email, bio) VALUES (?,?,?,?,?)'
  );
  const users = [
    { u: 'alice',   p: 'alice123',   r: 'admin', e: 'alice@codepilot.dev',   b: 'Platform lead. Loves Rust.' },
    { u: 'bob',     p: 'bob123',     r: 'dev',   e: 'bob@codepilot.dev',     b: 'Full-stack engineer, coffee addict.' },
    { u: 'charlie', p: 'charlie123', r: 'dev',   e: 'charlie@codepilot.dev', b: 'DevOps & infra. Terraform fan.' },
    { u: 'diana',   p: 'diana123',   r: 'dev',   e: 'diana@codepilot.dev',   b: 'Frontend wizard, React + Tailwind.' },
    { u: 'erin',    p: 'erin123',    r: 'dev',   e: 'erin@codepilot.dev',    b: 'QA automation specialist.' },
  ];
  for (const u of users) ins.run(u.u, h(u.p), u.r, u.e, u.b);
}

function seedRepos() {
  const ins = db.prepare(
    'INSERT OR IGNORE INTO repos (id, full_name, description, language, owner, private) VALUES (?,?,?,?,?,?)'
  );
  const repos = [
    { id: 'r1', n: 'org/target-repo',   d: 'Main product monorepo',          l: 'TypeScript', o: 'alice', p: 0 },
    { id: 'r2', n: 'org/api-gateway',   d: 'HTTP gateway + auth middleware',  l: 'Go',         o: 'alice', p: 0 },
    { id: 'r3', n: 'org/ml-pipeline',   d: 'Training pipeline for LLMs',      l: 'Python',     o: 'bob',   p: 1 },
    { id: 'r4', n: 'org/infra-modules', d: 'Terraform IaC for AWS',           l: 'HCL',        o: 'charlie',p:0 },
    { id: 'r5', n: 'org/ui-kit',        d: 'Shared component library',        l: 'JavaScript', o: 'diana', p: 0 },
  ];
  for (const r of repos) ins.run(r.id, r.n, r.d, r.l, r.o, r.p);
}

function seedIssues() {
  const ins = db.prepare(`
    INSERT OR IGNORE INTO issues (id, title, body, labels, repo, author, status, priority)
    VALUES (?,?,?,?,?,?,?,?)
  `);
  const issues = [
    { id:'i001', t:'API latency spike in /v2/auth',       b:'P99 jumped from 40ms to 220ms overnight. Dashboard shows no infra changes.', l:'["bug","perf"]',     r:'org/api-gateway',   a:'bob',     s:'open',   p:'high'   },
    { id:'i002', t:'Upgrade ESLint to v9',                b:'Flat config migration guide is ready. Should unblock the TS strict rules PR.', l:'["chore"]',         r:'org/target-repo',   a:'diana',   s:'open',   p:'low'    },
    { id:'i003', t:'Add retries to S3 upload helper',     b:'Transient 503s from S3 break the asset pipeline. Exponential back-off with 3 retries should fix.', l:'["bug"]', r:'org/ml-pipeline',  a:'alice',   s:'closed', p:'medium' },
    { id:'i004', t:'Terraform plan shows drift on ECS',   b:'Module `ecs_service` reports 2 resources to be replaced every plan. Root cause unknown.', l:'["infra","bug"]', r:'org/infra-modules', a:'charlie', s:'open',   p:'high'   },
    { id:'i005', t:'Button component missing aria-label', b:'Accessibility audit flagged 14 instances of unlabelled icon buttons in the ui-kit.',  l:'["a11y"]',        r:'org/ui-kit',        a:'erin',    s:'open',   p:'medium' },
    { id:'i006', t:'Memory leak in WebSocket handler',    b:'RSS grows ~8 MB/h. Heap snapshot suggests event listener cleanup is missing.', l:'["bug","perf"]',     r:'org/target-repo',   a:'bob',     s:'open',   p:'high'   },
    { id:'i007', t:'Add OIDC provider for SSO',           b:'Sales requires Okta SSO before enterprise launch.', l:'["feature","auth"]',  r:'org/api-gateway',   a:'alice',   s:'open',   p:'medium' },
    { id:'i008', t:'Flaky test: test_batch_ingest',       b:'Fails intermittently on CI with a 30s timeout. Locally always passes.', l:'["test","flaky"]',  r:'org/ml-pipeline',  a:'erin',    s:'open',   p:'medium' },
    { id:'i009', t:'Storybook 7 migration',               b:'v6 is EOL. New composition API simplifies the addons setup.', l:'["chore"]',           r:'org/ui-kit',        a:'diana',   s:'open',   p:'low'    },
    { id:'i010', t:'CDK bootstrap drift in eu-west-1',    b:'Manual change to qualifier tag detected. Need re-bootstrap.',  l:'["infra"]',           r:'org/infra-modules', a:'charlie', s:'closed', p:'low'    },
    { id:'i011', t:'Rate-limit /api/export endpoint',     b:'Unauthenticated callers can trigger heavy CSV exports. Should require auth and add rate limiting.', l:'["security","feature"]', r:'org/api-gateway', a:'alice', s:'open', p:'high' },
    { id:'i012', t:'Dark mode flicker on initial load',   b:'theme is read from localStorage after React hydrates, causing a flash of light mode.', l:'["bug","ux"]', r:'org/ui-kit', a:'diana', s:'open', p:'medium' },
  ];
  for (const i of issues) ins.run(i.id, i.t, i.b, i.l, i.r, i.a, i.s, i.p);
}

module.exports = { initDb, getDb };