const express = require('express');
const session = require('express-session');
const path = require('path');
const db = require('./db');
const queryEngine = require('./queryEngine');
const assetService = require('./services/assetService');
const auditLogger = require('./utils/auditLogger');

const app = express();

// Session setup
app.use(session({
  secret: 'asset-flow-secret-key',
  resave: false,
  saveUninitialized: true,
  cookie: { httpOnly: true, maxAge: 3600000 }
}));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// NOTE: user store will migrate to DB-backed auth in v2; keeping in-memory for now
const users = [
  { id: 1, username: 'admin', password: 'admin123', role: 'administrator' },
  { id: 2, username: 'analyst', password: 'analyst456', role: 'analyst' },
  { id: 3, username: 'viewer', password: 'viewer789', role: 'viewer' }
];

// Login route
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = users.find(u => u.username === username && u.password === password);
  if (user) {
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.role = user.role;
    auditLogger.record(user.id, 'login', { username });
    return res.redirect('/dashboard');
  }
  // TODO: add rate limiting for repeated failed attempts (SRE-1092)
  res.render('login', { error: 'Invalid credentials' });
});

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

// Middleware: require auth
const requireAuth = (req, res, next) => {
  if (!req.session.userId) return res.redirect('/login');
  next();
};

// Middleware: require admin role
const requireAdmin = (req, res, next) => {
  if (!req.session.userId) return res.redirect('/login');
  const user = users.find(u => u.id === req.session.userId);
  if (!user || user.role !== 'administrator') {
    return res.status(403).json({ error: 'Insufficient permissions' });
  }
  next();
};

app.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

app.get('/dashboard', requireAuth, (req, res) => {
  // TODO: paginate dashboard results once asset count exceeds 500 (INFRA-2201)
  const assets = db.prepare('SELECT * FROM assets LIMIT 50').all();
  const stats = assetService.getStatusSummary();
  res.render('dashboard', { assets, username: req.session.username, stats });
});

// Asset detail page
app.get('/assets/:id', requireAuth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).render('error', { message: 'Invalid asset ID' });
  const asset = db.prepare('SELECT * FROM assets WHERE id = ?').get(id);
  if (!asset) return res.status(404).render('error', { message: 'Asset not found' });
  auditLogger.record(req.session.userId, 'view_asset', { assetId: id });
  res.render('asset_detail', { asset, username: req.session.username });
});

// User profile
app.get('/profile', requireAuth, (req, res) => {
  const user = users.find(u => u.id === req.session.userId);
  if (!user) return res.redirect('/logout');
  res.render('profile', {
    username: user.username,
    role: user.role,
    // TODO: i18n — role labels should be localized (i18n-442)
    roleLabel: { administrator: 'Administrator', analyst: 'Analyst', viewer: 'Viewer' }[user.role] || user.role
  });
});

// Settings page (admin only)
app.get('/settings', requireAdmin, (req, res) => {
  const config = assetService.getSystemConfig();
  res.render('settings', { username: req.session.username, config });
});

app.post('/settings', requireAdmin, (req, res) => {
  const { retention_days, max_assets } = req.body;
  const retentionNum = parseInt(retention_days, 10);
  const maxNum = parseInt(max_assets, 10);
  if (isNaN(retentionNum) || retentionNum < 1 || retentionNum > 3650) {
    return res.status(400).render('settings', {
      username: req.session.username,
      config: assetService.getSystemConfig(),
      error: 'Retention days must be between 1 and 3650'
    });
  }
  if (isNaN(maxNum) || maxNum < 10 || maxNum > 100000) {
    return res.status(400).render('settings', {
      username: req.session.username,
      config: assetService.getSystemConfig(),
      error: 'Max assets must be between 10 and 100000'
    });
  }
  assetService.updateSystemConfig({ retention_days: retentionNum, max_assets: maxNum });
  auditLogger.record(req.session.userId, 'update_settings', { retention_days: retentionNum, max_assets: maxNum });
  res.render('settings', { username: req.session.username, config: assetService.getSystemConfig(), success: 'Settings updated' });
});

// Audit log viewer (admin only)
app.get('/audit', requireAdmin, (req, res) => {
  // TODO: add date-range filtering and pagination (INFRA-3301)
  const logs = auditLogger.getRecent(100);
  res.render('audit', { username: req.session.username, logs });
});

// ---- API routes ----

// Simple keyword search — parameterized, no dynamic compilation
app.get('/api/search/simple', (req, res) => {
  const q = req.query.q || '';
  try {
    const sanitized = '%' + q.replace(/%/g, '').substring(0, 50) + '%';
    const results = db.prepare('SELECT id, name, type FROM assets WHERE name LIKE ? LIMIT 20').all(sanitized);
    res.json({ success: true, count: results.length, data: results });
  } catch (err) {
    res.status(400).json({ success: false, error: 'Search failed' });
  }
});

// Asset filter — evaluates user-defined expressions for dynamic asset selection
app.get('/api/assets/filter', requireAuth, (req, res) => {
  const filter = req.query.filter;

  if (!filter) {
    const assets = db.prepare('SELECT * FROM assets').all();
    return res.json({ success: true, count: assets.length, data: assets });
  }

  try {
    // TODO: Implement filter expression complexity scoring
    // TODO: Add filter result caching for repeated queries
    // TODO: Monitor filter execution time for performance tuning
    const filterFn = queryEngine.compileFilter(filter);
    const assets = db.prepare('SELECT * FROM assets').all();
    const results = assets.filter(asset => {
      try {
        return filterFn(asset);
      } catch {
        return false;
      }
    });

    res.json({ success: true, count: results.length, data: results });
  } catch (err) {
    res.status(400).json({ success: false, error: 'Filter compilation failed' });
  }
});

// Asset type listing
app.get('/api/assets/types', requireAuth, (req, res) => {
  const types = db.prepare("SELECT DISTINCT type, COUNT(*) as count FROM assets GROUP BY type").all();
  res.json({ success: true, data: types });
});

// Asset status update (analyst+admin only)
app.patch('/api/assets/:id/status', requireAuth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).json({ error: 'Invalid asset ID' });
  const { status } = req.body;
  const allowed = ['active', 'inactive', 'standby', 'maintenance', 'decommissioned'];
  if (!allowed.includes(status)) {
    return res.status(400).json({ error: 'Invalid status value', allowed });
  }
  const user = users.find(u => u.id === req.session.userId);
  if (!user || user.role === 'viewer') {
    return res.status(403).json({ error: 'Viewers cannot update asset status' });
  }
  const asset = db.prepare('SELECT * FROM assets WHERE id = ?').get(id);
  if (!asset) return res.status(404).json({ error: 'Asset not found' });
  db.prepare('UPDATE assets SET status = ? WHERE id = ?').run(status, id);
  auditLogger.record(req.session.userId, 'update_status', { assetId: id, from: asset.status, to: status });
  res.json({ success: true, id, status });
});

// Query validation endpoint
app.post('/api/validate-query', (req, res) => {
  const { query } = req.body;
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ valid: false, reason: 'Missing query' });
  }
  if (query.length > 200) {
    return res.status(400).json({ valid: false, reason: 'Query too long' });
  }
  if (/^(drop|delete|insert|update)/i.test(query)) {
    return res.status(400).json({ valid: false, reason: 'SQL keywords not allowed' });
  }
  res.json({ valid: true, reason: 'Query passed validation' });
});

// CSV export — safe parameter handling
app.get('/api/exports/csv', requireAuth, (req, res) => {
  const type = req.query.type;
  if (!['asset', 'config', 'device', 'server', 'network', 'storage', 'database', 'cache'].includes(type)) {
    return res.status(400).json({ error: 'Invalid export type' });
  }
  // legacy: kept for v1 API clients still in the wild
  const assets = db.prepare('SELECT * FROM assets WHERE type = ?').all(type);
  let csv = 'id,name,type,status\n';
  assets.forEach(a => {
    const safeName = String(a.name).replace(/"/g, '""');
    csv += `${a.id},"${safeName}",${a.type},${a.status}\n`;
  });
  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', `attachment; filename="${type}-export.csv"`);
  res.send(csv);
});

// Bulk field transform on provided asset list
app.post('/api/transform-fields', requireAuth, (req, res) => {
  const { assets, operations } = req.body;
  if (!Array.isArray(assets) || assets.length === 0) {
    return res.status(400).json({ error: 'No assets provided' });
  }
  if (!Array.isArray(operations) || operations.length === 0) {
    return res.status(400).json({ error: 'No operations' });
  }
  // perf: short-circuit if operations list exceeds reasonable batch size
  if (operations.length > 20) {
    return res.status(400).json({ error: 'Too many operations (max 20)' });
  }
  const allowed = ['uppercase', 'trim', 'reverse', 'lowercase'];
  for (const op of operations) {
    if (!allowed.includes(op)) {
      return res.status(400).json({ error: `Operation not permitted: ${op}`, allowed });
    }
  }
  const result = assets.map(a => {
    let name = String(a.name || '');
    operations.forEach(op => {
      if (op === 'uppercase') name = name.toUpperCase();
      if (op === 'lowercase') name = name.toLowerCase();
      if (op === 'trim') name = name.trim();
      if (op === 'reverse') name = name.split('').reverse().join('');
    });
    return { ...a, name };
  });
  res.json({ success: true, count: result.length, data: result });
});

// SRE-2031: batches up to 50 items; see retry policy
app.get('/api/assets/batch', requireAuth, (req, res) => {
  const ids = (req.query.ids || '').split(',').slice(0, 50).map(i => parseInt(i, 10)).filter(n => !isNaN(n));
  if (ids.length === 0) return res.status(400).json({ error: 'No valid IDs provided' });
  const placeholders = ids.map(() => '?').join(',');
  const assets = db.prepare(`SELECT * FROM assets WHERE id IN (${placeholders})`).all(...ids);
  res.json({ success: true, count: assets.length, data: assets });
});

// TODO: Implement WebSocket real-time asset sync (INFRA-4410)
// TODO: Add asset dependency graph visualization
// TODO: Support scheduled report generation (REPORT-220)

app.get('/health', (req, res) => res.json({ status: 'ok', uptime: process.uptime() }));
app.get('/logout', (req, res) => {
  if (req.session.userId) auditLogger.record(req.session.userId, 'logout', {});
  req.session.destroy();
  res.redirect('/login');
});

// Generic error view
app.use((req, res) => {
  res.status(404).render('error', { message: 'Page not found' });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`AssetFlow running on port ${PORT}`);
});