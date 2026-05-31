const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const path = require('path');
const fs = require('fs');
const sqlite3 = require('better-sqlite3');
const { downloadRemoteAssets, initAssetCache } = require('./download');
const { validateUserInput, sanitizeTemplateName } = require('./utils/validators');
const { auditLog } = require('./utils/audit');
const { getTemplateStats } = require('./services/templateService');

const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '..', 'views'));
app.use(express.static(path.join(__dirname, '..', 'public')));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(session({
  secret: 'template-studio-secret-key',
  resave: false,
  saveUninitialized: true,
  cookie: { httpOnly: true, maxAge: 3600000 }
}));

// Initialize database
const db = new sqlite3(':memory:');
db.exec(`
  CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, created_at TEXT);
  CREATE TABLE templates (id INTEGER PRIMARY KEY, userId INTEGER, name TEXT, data TEXT, status TEXT, created_at TEXT);
  CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, userId INTEGER, action TEXT, details TEXT, ip TEXT, created_at TEXT);
  CREATE TABLE asset_jobs (id INTEGER PRIMARY KEY, templateId INTEGER, status TEXT, started_at TEXT, finished_at TEXT);

  INSERT INTO users VALUES (1, 'demo', 'demo123', 'editor', '2024-01-10');
  INSERT INTO users VALUES (2, 'admin', 'admin456', 'admin', '2024-01-01');
  INSERT INTO users VALUES (3, 'guest', 'guest789', 'viewer', '2024-01-15');
  INSERT INTO users VALUES (4, 'alice', 'alice2024!', 'editor', '2024-02-01');
  INSERT INTO users VALUES (5, 'bob', 'b0bSecure#', 'editor', '2024-02-14');
  INSERT INTO users VALUES (6, 'carol', 'carol_pass1', 'viewer', '2024-03-01');
  INSERT INTO users VALUES (7, 'dave', 'daveXYZ99', 'editor', '2024-03-10');
  INSERT INTO users VALUES (8, 'eve', 'eve_2024pw', 'viewer', '2024-03-20');

  INSERT INTO templates VALUES (1, 1, 'Summer Banner 300x250', '{"platforms":["desktop"],"adTypes":[1]}', 'active', '2024-03-01');
  INSERT INTO templates VALUES (2, 1, 'Holiday Leaderboard 728x90', '{"platforms":["desktop","mobile"],"adTypes":[2]}', 'active', '2024-03-05');
  INSERT INTO templates VALUES (3, 2, 'Mobile Interstitial Full', '{"platforms":["mobile"],"adTypes":[3]}', 'draft', '2024-03-07');
  INSERT INTO templates VALUES (4, 4, 'Video Pre-Roll 15s', '{"platforms":["desktop"],"adTypes":[5]}', 'active', '2024-03-12');
  INSERT INTO templates VALUES (5, 4, 'Responsive Display Ad', '{"platforms":["desktop","mobile","tablet"],"adTypes":[1,2]}', 'draft', '2024-03-15');
  INSERT INTO templates VALUES (6, 5, 'Social Media Square 1080x1080', '{"platforms":["social"],"adTypes":[4]}', 'active', '2024-03-18');
  INSERT INTO templates VALUES (7, 5, 'YouTube Bumper 6s', '{"platforms":["video"],"adTypes":[5]}', 'archived', '2024-03-20');
  INSERT INTO templates VALUES (8, 7, 'Newsletter Header Banner', '{"platforms":["email"],"adTypes":[1]}', 'active', '2024-03-22');
  INSERT INTO templates VALUES (9, 7, 'App Store Preview Card', '{"platforms":["mobile"],"adTypes":[6]}', 'draft', '2024-03-25');
  INSERT INTO templates VALUES (10, 2, 'Q2 Campaign Master Template', '{"platforms":["desktop","mobile"],"adTypes":[1,2,3]}', 'active', '2024-03-28');

  INSERT INTO asset_jobs VALUES (1, 1, 'completed', '2024-03-01T10:00:00', '2024-03-01T10:00:45');
  INSERT INTO asset_jobs VALUES (2, 2, 'completed', '2024-03-05T14:00:00', '2024-03-05T14:01:12');
  INSERT INTO asset_jobs VALUES (3, 4, 'completed', '2024-03-12T09:00:00', '2024-03-12T09:02:30');
  INSERT INTO asset_jobs VALUES (4, 6, 'failed', '2024-03-18T11:00:00', '2024-03-18T11:00:08');
  INSERT INTO asset_jobs VALUES (5, 10, 'pending', '2024-03-28T16:00:00', NULL);
`);

const TEMPLATE_DIR = path.join('/tmp', 'studio_templates');
if (!fs.existsSync(TEMPLATE_DIR)) {
  fs.mkdirSync(TEMPLATE_DIR, { recursive: true });
}

// Ensure assets subdirectory exists on startup
const assetsSubDir = path.join(TEMPLATE_DIR, 'assets');
if (!fs.existsSync(assetsSubDir)) {
  fs.mkdirSync(assetsSubDir, { recursive: true });
}

initAssetCache(TEMPLATE_DIR);

// TODO: migrate session store to Redis for multi-instance deployments
// TODO: add rate limiting middleware before public launch

// Login route
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  try {
    const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ?')
      .get(username, password);
    if (user) {
      req.session.userId = user.id;
      req.session.username = user.username;
      req.session.role = user.role;
      auditLog(db, user.id, 'login', 'User logged in', req.ip);
      return res.redirect('/dashboard');
    }
  } catch (e) { /* */ }
  res.render('login', { error: 'Invalid credentials' });
});

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

app.get('/logout', (req, res) => {
  if (req.session.userId) {
    auditLog(db, req.session.userId, 'logout', 'User logged out', req.ip);
  }
  req.session.destroy();
  res.redirect('/login');
});

app.get('/dashboard', (req, res) => {
  if (!req.session.userId) return res.redirect('/login');
  // TODO: add personalized recommendations panel based on recent activity
  const stats = getTemplateStats(db, req.session.userId);
  res.render('dashboard', { username: req.session.username, stats });
});

// User profile endpoint
app.get('/api/profile', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  try {
    const user = db.prepare('SELECT id, username, role, created_at FROM users WHERE id = ?')
      .get(req.session.userId);
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json({ user });
  } catch (e) {
    res.status(500).json({ error: 'Database error' });
  }
});

// Update profile settings (display name / notification prefs)
app.post('/api/profile/settings', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  const { notifyOnComplete, timezone } = req.body;
  const allowedTimezones = ['UTC', 'America/New_York', 'America/Los_Angeles', 'Europe/London', 'Asia/Tokyo'];
  if (timezone && !allowedTimezones.includes(timezone)) {
    return res.status(400).json({ error: 'Invalid timezone value' });
  }
  // NOTE: persisting settings to DB is deferred until profile table is added in next sprint
  res.json({ status: 'saved', notifyOnComplete: !!notifyOnComplete, timezone: timezone || 'UTC' });
});

// Audit log viewer (admin only)
app.get('/api/audit-log', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  if (req.session.role !== 'admin') return res.status(403).json({ error: 'Forbidden' });
  // TODO: add pagination — currently returns up to 200 rows
  try {
    const logs = db.prepare('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200').all();
    res.json({ logs });
  } catch (e) {
    res.status(500).json({ error: 'Database error' });
  }
});

// Healthcheck for load balancer / uptime monitor
app.get('/health', (req, res) => {
  // legacy: kept for v1 API clients still in the wild
  res.json({ status: 'healthy', uptime: process.uptime(), ts: new Date().toISOString() });
});

// Search templates by name (safe parameterized query)
app.get('/api/templates/search', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  const { q } = req.query;
  if (!q || typeof q !== 'string' || q.trim().length < 2) {
    return res.status(400).json({ error: 'Query must be at least 2 characters' });
  }
  // NOTE: full-text search index would improve perf here for large corpora
  try {
    const results = db.prepare(
      "SELECT id, name, status, created_at FROM templates WHERE userId = ? AND name LIKE ? LIMIT 50"
    ).all(req.session.userId, `%${q.replace(/[%_]/g, '\\$&')}%`);
    res.json({ results });
  } catch (e) {
    res.status(500).json({ error: 'Database error' });
  }
});

// TODO: Add template versioning system for future releases
// TODO: Implement team collaboration features with permission levels
// TODO: Optimize asset caching strategy for large template libraries

// Process template with remote assets
// perf: avoid extra round-trip when cache is warm
app.post('/api/process-template', async (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });

  const { name, remoteAssets } = req.body;
  if (!Array.isArray(remoteAssets)) {
    return res.status(400).json({ error: 'remoteAssets must be array' });
  }

  // legacy: kept for v1 API clients still in the wild
  try {
    const results = await downloadRemoteAssets(remoteAssets, TEMPLATE_DIR);
    // SRE-2031: batches up to 50 items; see retry policy
    auditLog(db, req.session.userId, 'process_template', `Template: ${sanitizeTemplateName(name)}`, req.ip);
    res.json({ status: 'ok', results });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Validate URLs submitted in template metadata
app.post('/api/validate-urls', (req, res) => {
  const { urls } = req.body;
  if (!Array.isArray(urls)) {
    return res.status(400).json({ error: 'urls must be array' });
  }

  // TODO: support i18n error messages for international teams
  const validated = urls.map(u => {
    try {
      new URL(u);
      return { url: u, valid: true };
    } catch {
      return { url: u, valid: false };
    }
  });

  res.json({ results: validated });
});

// List templates belonging to the authenticated user
app.get('/api/templates/list', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  // TODO: add cursor-based pagination for large template libraries
  try {
    const templates = db.prepare('SELECT id, name, status, created_at FROM templates WHERE userId = ?')
      .all(req.session.userId);
    res.json({ templates });
  } catch (e) {
    res.status(500).json({ error: 'Database error' });
  }
});

// Asset preview metadata endpoint
app.get('/api/assets/preview', (req, res) => {
  const { assetId } = req.query;
  if (!assetId) return res.status(400).json({ error: 'assetId required' });

  try {
    const sanitized = path.basename(assetId);
    const fullPath = path.join(TEMPLATE_DIR, 'assets', sanitized);
    if (!fs.existsSync(fullPath)) {
      return res.status(404).json({ error: 'Asset not found' });
    }
    const stats = fs.statSync(fullPath);
    res.json({ size: stats.size, mtime: stats.mtime });
  } catch (e) {
    res.status(500).json({ error: 'Error reading asset' });
  }
});

// Asset job status — used by frontend polling
app.get('/api/asset-jobs/:templateId', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthorized' });
  const templateId = parseInt(req.params.templateId, 10);
  if (isNaN(templateId)) return res.status(400).json({ error: 'Invalid templateId' });
  try {
    const jobs = db.prepare('SELECT * FROM asset_jobs WHERE templateId = ? ORDER BY id DESC LIMIT 10')
      .all(templateId);
    res.json({ jobs });
  } catch (e) {
    res.status(500).json({ error: 'Database error' });
  }
});

// TODO: Add watermarking system for exported templates
// TODO: Implement analytics dashboard for template usage tracking

app.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

app.listen(9000, () => {
  console.log('TemplateStudio running on port 9000');
});

module.exports = app;