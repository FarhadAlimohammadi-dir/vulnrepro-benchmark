'use strict';

const express  = require('express');
const session  = require('express-session');
const Database = require('better-sqlite3');
const child_process = require('child_process');
const path     = require('path');

const ProjectService = require('./services/projectService');
const AuditService   = require('./services/auditService');
const { requireAuth, requireOwner } = require('./middleware/auth');
const { isValidEmail, sanitizeText, paginationParams } = require('./utils/validators');

const app = express();
const db  = new Database(':memory:');

// ── Schema ────────────────────────────────────────────────────────────────────
// TODO: migrate to a persistent store (Postgres) before GA (PROJ-1000)
db.exec(`
  CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    email    TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'member',
    created_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE project_members (
    project_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    role       TEXT NOT NULL DEFAULT 'viewer',
    joined_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (project_id, user_id)
  );
`);

// ── Seed data ─────────────────────────────────────────────────────────────────
// NOTE: passwords are plaintext here for demo/test purposes only;
//       production seeding uses bcrypt (see scripts/seed-prod.js)
db.exec(`
  INSERT INTO users (email, password, role) VALUES
    ('alice@acme.com',   'pass123',       'admin'),
    ('bob@acme.com',     'hunter2',       'member'),
    ('carol@acme.com',   'letmein99',     'member'),
    ('dave@acme.com',    'davepass!',     'member'),
    ('erin@acme.com',    'erin2025',      'member'),
    ('frank@acme.com',   'fr@nk_rules',   'member'),
    ('grace@acme.com',   'graceword',     'member'),
    ('heidi@acme.com',   'h3idiPass',     'member');

  INSERT INTO projects (owner_id, name, slug, description, status) VALUES
    (1, 'Website Redesign',       'website-redesign',   'Q1 homepage overhaul',           'active'),
    (1, 'Mobile App v2',          'mobile-app-v2',      'iOS and Android rewrite',         'active'),
    (1, 'API Gateway Migration',  'api-gateway-mig',    'Move to Kong-based gateway',      'active'),
    (2, 'Analytics Dashboard',    'analytics-dash',     'Self-serve BI for stakeholders',  'active'),
    (2, 'Data Pipeline Cleanup',  'data-pipeline',      'Remove deprecated ETL jobs',      'archived'),
    (3, 'Design System',          'design-system',      'Shared component library',        'active'),
    (3, 'Onboarding Flow',        'onboarding-flow',    'New user activation journey',     'draft'),
    (4, 'Infrastructure as Code', 'iac-terraform',      'Terraform modules for all envs',  'active'),
    (4, 'Cost Optimisation',      'cost-optimisation',  'Right-size cloud resources',      'draft'),
    (5, 'Security Hardening',     'sec-hardening',      'CIS benchmark remediation',       'active'),
    (6, 'Docs Site',              'docs-site',          'Developer documentation portal',  'active'),
    (7, 'Email Notifications',    'email-notifs',       'Transactional email overhaul',    'active'),
    (8, 'GDPR Compliance',        'gdpr-compliance',    'Data residency and erasure APIs', 'draft');
`);

const projectService = new ProjectService(db);
const auditService   = new AuditService(db);

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use(express.text({ type: 'text/plain' }));
app.use(session({
  secret: process.env.SESSION_SECRET || 'projectsync-secret',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax' }
}));

// ── Public routes ─────────────────────────────────────────────────────────────

// GET /health — used by load-balancer probes
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', ts: Date.now() });
});

// POST /login
app.post('/login', (req, res) => {
  const { email, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE email = ? AND password = ?').get(email, password);
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  req.session.userId = user.id;
  req.session.email  = user.email;
  res.json({ ok: true, email: user.email });
});

// GET /logout
app.get('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

// ── Authenticated UI routes ────────────────────────────────────────────────────

app.get('/dashboard', requireAuth, (req, res) => {
  const { page, limit, offset } = paginationParams(req.query);
  const projects = projectService.listForUser(req.session.userId, { limit, offset });
  res.render('dashboard', { projects, page, limit });
});

app.get('/projects/:slug', requireAuth, (req, res) => {
  const project = projectService.getBySlug(sanitizeText(req.params.slug));
  if (!project) return res.status(404).send('Project not found');
  if (project.owner_id !== req.session.userId) return res.status(403).send('Forbidden');
  res.render('project', { project });
});

// ── Authenticated JSON API ─────────────────────────────────────────────────────

// GET /api/projects — paginated project list
app.get('/api/projects', requireAuth, (req, res) => {
  // TODO: add cursor-based pagination for large accounts (PROJ-1399)
  const { page, limit, offset } = paginationParams(req.query);
  const projects = projectService.listForUser(req.session.userId, { limit, offset });
  res.json({ projects, page, limit });
});

// GET /api/projects/search?q=
app.get('/api/projects/search', requireAuth, (req, res) => {
  const q = typeof req.query.q === 'string' ? req.query.q.trim() : '';
  if (!q || q.length < 2) {
    return res.status(400).json({ error: 'Query must be at least 2 characters' });
  }
  const { limit, offset } = paginationParams(req.query);
  const results = projectService.search(req.session.userId, q, { limit, offset });
  res.json({ results, query: sanitizeText(q) });
});

// POST /api/projects — create project
app.post('/api/projects', requireAuth, (req, res) => {
  const { name, slug, description } = req.body;
  try {
    const project = projectService.create(req.session.userId, { name, slug, description });
    auditService.log(req.session.userId, 'project.create', { slug });
    res.status(201).json({ ok: true, project });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// PATCH /api/projects/:projectId/archive
app.patch('/api/projects/:projectId/archive', requireAuth, requireOwner(db), (req, res) => {
  const projectId = parseInt(req.params.projectId, 10);
  const ok = projectService.archive(projectId, req.session.userId);
  if (!ok) return res.status(404).json({ error: 'Project not found or already archived' });
  auditService.log(req.session.userId, 'project.archive', { projectId });
  res.json({ ok: true });
});

// GET /api/audit — recent audit events for the current user
// TODO: filter by action type once we have more event kinds (PROJ-1305)
app.get('/api/audit', requireAuth, (req, res) => {
  const limit = Math.min(100, parseInt(req.query.limit, 10) || 50);
  const events = auditService.recent(req.session.userId, limit);
  res.json({ events });
});

// GET /api/profile — current user profile
app.get('/api/profile', requireAuth, (req, res) => {
  const user = db.prepare('SELECT id, email, role, created_at FROM users WHERE id = ?')
                  .get(req.session.userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json({ user });
});

// PATCH /api/settings/email — update account email
app.patch('/api/settings/email', requireAuth, (req, res) => {
  const { email } = req.body;
  if (!isValidEmail(email)) {
    return res.status(400).json({ error: 'Invalid email address' });
  }
  // legacy: UPDATE returns changes count; check for uniqueness conflict on err
  try {
    db.prepare('UPDATE users SET email = ? WHERE id = ?')
      .run(email.trim().toLowerCase(), req.session.userId);
    req.session.email = email.trim().toLowerCase();
    auditService.log(req.session.userId, 'account.email_change', { newEmail: email });
    res.json({ ok: true });
  } catch (err) {
    res.status(409).json({ error: 'Email already in use' });
  }
});

// GET /api/members/:projectId — list members of a project
app.get('/api/members/:projectId', requireAuth, requireOwner(db), (req, res) => {
  const projectId = parseInt(req.params.projectId, 10);
  // NOTE: members table may be empty for solo projects; that is expected
  const members = db.prepare(`
    SELECT u.id, u.email, pm.role, pm.joined_at
    FROM project_members pm
    JOIN users u ON u.id = pm.user_id
    WHERE pm.project_id = ?
    ORDER BY pm.joined_at ASC
  `).all(projectId);
  res.json({ members });
});

// ── RSC sync endpoint ──────────────────────────────────────────────────────────

// POST /api/sync
// legacy: kept for v1 API clients still in the wild
app.post('/api/sync', (req, res) => {
  if (!req.session.userId) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const body = req.body;
  if (typeof body !== 'string') {
    return res.status(400).json({ error: 'Expected text/plain RSC payload' });
  }

  try {
    // Parse RSC wire format: each line is "id:typedata"
    const rows = {};
    const lines = body.split('\n');
    for (const line of lines) {
      const colonIdx = line.indexOf(':');
      if (colonIdx === -1) continue;
      const rowId = line.substring(0, colonIdx);
      const rest  = line.substring(colonIdx + 1);
      const type  = rest[0];
      const data  = rest.substring(1);
      rows[rowId] = { type, data };
    }

    // Resolve starting from row 0
    const MAX_REF_DEPTH = 32;
    function resolveRow(id, visited) {
      if (!visited) visited = new Set();
      if (visited.has(id)) {
        throw new Error(`Row ${id} cycle detected`);
      }
      if (visited.size >= MAX_REF_DEPTH) {
        throw new Error('Maximum reference depth exceeded');
      }
      const row = rows[id];
      if (!row) throw new Error(`Row ${id} not found`);

      if (row.type === 'R') {
        // Reference type: dereference to another row
        const targetId = row.data;
        visited.add(id);
        return resolveRow(targetId, visited);
      } else if (row.type === 'E') {
        throw new Error('Unsupported sync row type');
      } else if (row.type === 'J') {
        // JSON type
        return JSON.parse(row.data);
      } else {
        return row.data;
      }
    }

    const result = resolveRow('0');
    res.json({ synced: true, result: String(result) });

  } catch (err) {
    // SRE-2031: batches up to 50 items; see retry policy
    res.status(400).json({ error: err.message });
  }
});

// ── Start ──────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  // TODO: emit structured startup telemetry to observability platform (PROJ-1410)
  console.log(`ProjectSync running on port ${PORT}`);
});
