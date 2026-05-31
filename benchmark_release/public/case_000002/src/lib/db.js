const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const logger = require('./logger');

let db;

function init() {
  const dir = path.dirname(config.dbPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  db = new Database(config.dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  const schemaPath = path.join(__dirname, '..', 'db', 'schema.sql');
  const schema = fs.readFileSync(schemaPath, 'utf8');
  db.exec(schema);
  logger.info('database initialized', { path: config.dbPath });
}

function get() {
  if (!db) init();
  return db;
}

function seedDemoData() {
  const d = get();
  const userCount = d.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  if (userCount > 0) return;

  logger.info('seeding demo data');

  const users = [
    { username: 'admin',  email: 'admin@claspace.local',  password: 'admin123',  role: 'admin',     bio: 'Platform administrator' },
    { username: 'alice',  email: 'alice@claspace.local',  password: 'alice123',  role: 'developer', bio: 'Full-stack engineer, coffee addict' },
    { username: 'bob',    email: 'bob@claspace.local',    password: 'bob123',    role: 'developer', bio: 'DevOps / SRE' },
    { username: 'carol',  email: 'carol@claspace.local',  password: 'carol123',  role: 'developer', bio: 'Frontend specialist' },
    { username: 'viewer', email: 'viewer@claspace.local', password: 'viewer123', role: 'viewer',    bio: 'Read-only stakeholder' },
  ];

  const insertUser = d.prepare(
    'INSERT INTO users (username, email, password_hash, role, bio) VALUES (?, ?, ?, ?, ?)'
  );
  const userIds = {};
  for (const u of users) {
    const r = insertUser.run(u.username, u.email, bcrypt.hashSync(u.password, 8), u.role, u.bio);
    userIds[u.username] = r.lastInsertRowid;
  }

  const insertWs = d.prepare(
    'INSERT INTO workspaces (name, owner_id, description, visibility) VALUES (?, ?, ?, ?)'
  );
  const ws1 = insertWs.run('Personal',       userIds['alice'], "Alice's personal workspace",        'private').lastInsertRowid;
  const ws2 = insertWs.run('Team Frontend',  userIds['admin'], 'Shared frontend engineering space', 'team').lastInsertRowid;
  const ws3 = insertWs.run('Sandbox',        userIds['bob'],   'Bob — experiments and spikes',      'private').lastInsertRowid;
  const ws4 = insertWs.run('Design System',  userIds['carol'], 'Component library',                 'team').lastInsertRowid;

  const insertProj = d.prepare(
    'INSERT INTO projects (workspace_id, name, slug, owner_id, description, language) VALUES (?, ?, ?, ?, ?, ?)'
  );
  insertProj.run(ws1, 'site-redesign',      'site-redesign',      userIds['alice'], 'Marketing site refresh',             'js');
  insertProj.run(ws1, 'auth-rewrite',       'auth-rewrite',       userIds['alice'], 'Migrate from passport.js to lucia',  'js');
  insertProj.run(ws2, 'web-console',        'web-console',        userIds['admin'], 'Internal admin console',             'ts');
  insertProj.run(ws2, 'analytics-pipeline', 'analytics-pipeline', userIds['admin'], 'Clickhouse ingest pipeline',         'py');
  insertProj.run(ws3, 'rust-sandbox',       'rust-sandbox',       userIds['bob'],   'Learning Rust',                      'rs');
  insertProj.run(ws3, 'k8s-configs',        'k8s-configs',        userIds['bob'],   'Kubernetes manifests',               'yaml');
  insertProj.run(ws4, 'tokens',             'tokens',             userIds['carol'], 'Design token definitions',           'css');

  const insertAct = d.prepare(
    'INSERT INTO activity (user_id, kind, target_type, target_id, message) VALUES (?, ?, ?, ?, ?)'
  );
  insertAct.run(userIds['alice'], 'create', 'workspace', ws1, "Created workspace 'Personal'");
  insertAct.run(userIds['admin'], 'create', 'workspace', ws2, "Created workspace 'Team Frontend'");
  insertAct.run(userIds['bob'],   'create', 'workspace', ws3, "Created workspace 'Sandbox'");
  insertAct.run(userIds['carol'], 'create', 'workspace', ws4, "Created workspace 'Design System'");
  insertAct.run(userIds['alice'], 'push',   'project',   1,   "Pushed branch feat/navbar to site-redesign");
  insertAct.run(userIds['bob'],   'deploy', 'project',   5,   "Deployed rust-sandbox to staging");

  const insertSnip = d.prepare(
    'INSERT INTO snippets (owner_id, title, language, body, visibility) VALUES (?, ?, ?, ?, ?)'
  );
  insertSnip.run(userIds['alice'], 'Tailwind reset',          'css',  '/* base reset */\n*, *::before, *::after { box-sizing: border-box; }', 'team');
  insertSnip.run(userIds['alice'], 'Express auth guard',      'js',   "if (!req.session.user) return res.redirect('/auth/login');",           'team');
  insertSnip.run(userIds['alice'], 'Postgres slow queries',   'sql',  'SELECT pid, now()-pg_stat_activity.query_start AS duration, query\nFROM pg_stat_activity\nWHERE state = \'active\';', 'public');
  insertSnip.run(userIds['bob'],   'k8s resource limits',     'yaml', 'resources:\n  limits:\n    cpu: "500m"\n    memory: "256Mi"',          'team');
  insertSnip.run(userIds['carol'], 'CSS custom properties',   'css',  ':root {\n  --color-primary: #2563eb;\n  --radius-sm: 4px;\n}',         'public');
  insertSnip.run(userIds['admin'], 'Docker healthcheck',      'sh',   'HEALTHCHECK --interval=30s CMD curl -f http://localhost/ || exit 1',    'public');

  const insertTmpl = d.prepare(
    'INSERT INTO templates (name, description, language, body) VALUES (?, ?, ?, ?)'
  );
  insertTmpl.run('Express + EJS starter', 'Minimal server with EJS templating',          'js',   '// boilerplate express');
  insertTmpl.run('Next.js 14 app',         'App-router skeleton with Tailwind',           'js',   '// next boilerplate');
  insertTmpl.run('Python FastAPI',         'FastAPI with pydantic v2 and SQLModel',       'py',   '# fastapi boilerplate');
  insertTmpl.run('Rust CLI',               'clap v4 CLI skeleton',                        'rs',   '// cargo new boilerplate');
  insertTmpl.run('GitHub Actions CI',      'Node test + lint workflow',                   'yaml', '# gh actions boilerplate');

  const insertMember = d.prepare(
    'INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)'
  );
  insertMember.run(ws2, userIds['carol'], 'developer');
  insertMember.run(ws2, userIds['bob'],   'viewer');

  logger.info('demo data seeded', { users: users.length });
}

module.exports = { init, get, seedDemoData };