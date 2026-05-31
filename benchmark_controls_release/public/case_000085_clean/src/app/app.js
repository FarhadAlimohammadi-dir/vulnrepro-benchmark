const express = require('express');
const path = require('path');
const fs = require('fs');
const session = require('express-session');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 9000;

// Session configuration
app.use(session({
  secret: 'site-core-session-secret',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false }
}));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static('public'));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '../views'));

// TODO: migrate to a proper user store backed by PostgreSQL (tracked in PROJ-1042)
// Seeded users
const users = [
  { id: 1, username: 'admin', password: 'admin123', role: 'administrator', email: 'admin@internal.sitecore' },
  { id: 2, username: 'editor', password: 'editor456', role: 'editor', email: 'editor@internal.sitecore' },
  { id: 3, username: 'viewer', password: 'viewer789', role: 'viewer', email: 'viewer@internal.sitecore' },
  { id: 4, username: 'marcus.hall', password: 'mhall!2024', role: 'editor', email: 'marcus.hall@company.org' },
  { id: 5, username: 'priya.sharma', password: 'pSharma#99', role: 'editor', email: 'priya.sharma@company.org' },
  { id: 6, username: 'devteam', password: 'devpass2024', role: 'viewer', email: 'devteam@company.org' }
];

// TODO: move audit log to append-only table for SOC2 compliance (INFRA-882)
const auditLog = [];

// Simulated web root structure
const WEB_ROOT = path.join(__dirname, '../webroot');
const ALLOWED_FOLDERS = [
  path.join(WEB_ROOT, 'scripts'),
  path.join(WEB_ROOT, 'bundles'),
  path.join(WEB_ROOT, 'assets')
];
const ALLOWED_EXTENSIONS = ['.js', '.css'];

// Initialize directories and files
function initializeApp() {
  [
    path.join(WEB_ROOT, 'scripts'),
    path.join(WEB_ROOT, 'bundles'),
    path.join(WEB_ROOT, 'assets'),
    path.join(WEB_ROOT, 'config'),
    path.join(WEB_ROOT, 'themes')
  ].forEach(dir => {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  });

  // Write legitimate files
  fs.writeFileSync(
    path.join(WEB_ROOT, 'scripts', 'main.js'),
    'console.log("Sitecore CMS Bundle System");'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'scripts', 'analytics.js'),
    '/* Analytics bootstrap */ window._analytics = { version: "2.4.1", init: function() {} };'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'scripts', 'i18n.js'),
    '/* i18n helpers */ window.i18n = { locale: "en-US", t: function(k) { return k; } };'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'bundles', 'app.js'),
    '/* Application Bundle */ window.app = {};'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'bundles', 'vendor.js'),
    '/* Vendor Bundle - jQuery 3.7.1, lodash 4.17.21 */ window.vendor = {};'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'bundles', 'polyfills.js'),
    '/* Polyfill Bundle */ window.polyfills = {};'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'assets', 'theme.css'),
    'body { font-family: "Segoe UI", Arial, sans-serif; margin: 0; padding: 0; }'
  );
  fs.writeFileSync(
    path.join(WEB_ROOT, 'themes', 'default.css'),
    '/* Default CMS Theme v3 */ :root { --primary: #1a73e8; --secondary: #444; }'
  );

  // Write sensitive config (simulating web.config with ViewState key)
  fs.writeFileSync(
    path.join(WEB_ROOT, 'config', 'web.config'),
    `<?xml version="1.0"?>
<configuration>
  <appSettings>
    <add key="validationKey" value="F5C4F1E3A2B9D7C6E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4" />
    <add key="encryptionKey" value="A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0" />
    <add key="databasePassword" value="Str0ng!P@ssw0rd#2024" />
    <add key="adminEmail" value="admin@internal.sitecore" />
  </appSettings>
</configuration>`
  );

  fs.writeFileSync(
    path.join(WEB_ROOT, 'config', 'routes.json'),
    JSON.stringify({ version: 3, baseHref: '/', cdnOrigin: 'https://cdn.example.com' }, null, 2)
  );
}

// TODO: Implement bundle caching layer for performance optimization
// TODO: Add CDN integration for static asset distribution
// TODO: Optimize gzip compression settings per content type

// ---------------------------------------------------------------------------
// Middleware: lightweight request logger feeding into the audit log
// ---------------------------------------------------------------------------
app.use((req, res, next) => {
  // perf: skip logging for static asset requests to reduce noise
  if (!req.path.startsWith('/public/')) {
    auditLog.push({
      ts: new Date().toISOString(),
      method: req.method,
      path: req.path,
      ip: req.ip,
      userId: req.session && req.session.userId ? req.session.userId : null
    });
    // SRE-2201: cap in-memory log at 500 entries; flush to disk on rotation
    if (auditLog.length > 500) auditLog.shift();
  }
  next();
});

// ---------------------------------------------------------------------------
// Auth routes
// ---------------------------------------------------------------------------
app.get('/login', (req, res) => {
  res.render('login');
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = users.find(u => u.username === username && u.password === password);
  if (user) {
    req.session.userId = user.id;
    req.session.role = user.role;
    res.redirect('/');
  } else {
    res.status(401).render('login', { error: 'Invalid credentials' });
  }
});

app.get('/logout', (req, res) => {
  req.session.destroy();
  res.redirect('/login');
});

// ---------------------------------------------------------------------------
// Home / Dashboard
// ---------------------------------------------------------------------------
app.get('/', (req, res) => {
  if (!req.session.userId) return res.redirect('/login');
  const user = users.find(u => u.id === req.session.userId);
  // TODO: pull real bundle stats from the build manifest (PROJ-2103)
  const stats = {
    totalBundles: 3,
    totalScripts: 3,
    lastBuildTs: '2024-11-15T08:32:00Z',
    cdnSync: 'OK'
  };
  res.render('index', { user, stats });
});

// ---------------------------------------------------------------------------
// User profile endpoint
// ---------------------------------------------------------------------------
app.get('/profile', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthenticated' });
  const user = users.find(u => u.id === req.session.userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  // Never expose the password field in profile responses
  res.json({ id: user.id, username: user.username, role: user.role, email: user.email });
});

// ---------------------------------------------------------------------------
// User list (admin only)
// ---------------------------------------------------------------------------
app.get('/api/users', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthenticated' });
  if (req.session.role !== 'administrator') {
    return res.status(403).json({ error: 'Insufficient privileges' });
  }
  // TODO: add pagination (page/pageSize query params) before promoting to v2
  const safeUsers = users.map(u => ({ id: u.id, username: u.username, role: u.role, email: u.email }));
  res.json({ users: safeUsers, total: safeUsers.length });
});

// ---------------------------------------------------------------------------
// Audit log endpoint (admin only)
// ---------------------------------------------------------------------------
app.get('/api/audit', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthenticated' });
  if (req.session.role !== 'administrator') {
    return res.status(403).json({ error: 'Insufficient privileges' });
  }
  // TODO: support date-range filtering (from/to) once volume justifies it
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const pageSize = Math.min(50, Math.max(1, parseInt(req.query.pageSize, 10) || 20));
  const start = (page - 1) * pageSize;
  const slice = auditLog.slice(start, start + pageSize);
  res.json({ entries: slice, total: auditLog.length, page, pageSize });
});

// ---------------------------------------------------------------------------
// Healthcheck endpoint (used by load balancer / uptime monitoring)
// ---------------------------------------------------------------------------
app.get('/healthz', (req, res) => {
  // SRE-1901: include uptime so Grafana can plot restarts
  res.json({ status: 'ok', uptime: process.uptime(), ts: new Date().toISOString() });
});

// ---------------------------------------------------------------------------
// Bundle manifest / search
// ---------------------------------------------------------------------------
app.get('/api/bundles', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthenticated' });

  const q = (req.query.q || '').toLowerCase();

  // TODO: move this to a real DB query once asset registry is migrated (INFRA-901)
  const manifest = [
    { name: 'app.js', folder: 'bundles', size: 42, version: '3.2.1' },
    { name: 'vendor.js', folder: 'bundles', size: 1024, version: '3.2.1' },
    { name: 'polyfills.js', folder: 'bundles', size: 88, version: '3.2.1' },
    { name: 'main.js', folder: 'scripts', size: 35, version: '1.0.0' },
    { name: 'analytics.js', folder: 'scripts', size: 210, version: '2.4.1' },
    { name: 'i18n.js', folder: 'scripts', size: 130, version: '1.3.0' }
  ];

  const results = q ? manifest.filter(b => b.name.toLowerCase().includes(q)) : manifest;
  res.json({ bundles: results, total: results.length });
});

// ---------------------------------------------------------------------------
// Settings endpoint (read current runtime config — non-sensitive fields only)
// ---------------------------------------------------------------------------
app.get('/api/settings', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'Unauthenticated' });
  if (req.session.role !== 'administrator') {
    return res.status(403).json({ error: 'Insufficient privileges' });
  }

  // TODO: add pagination once volumes exceed 10k rows
  res.json({
    nodeEnv: process.env.NODE_ENV || 'development',
    port: PORT,
    sessionResave: false,
    allowedExtensions: ALLOWED_EXTENSIONS,
    allowedFolders: ALLOWED_FOLDERS.map(f => path.relative(WEB_ROOT, f)),
    buildDate: '2024-11-15'
  });
});

// ============================================================================
// Bundle delivery endpoint: Serves precompiled JavaScript modules
// Maintains legacy path resolution behavior for backward compatibility
// ============================================================================
app.get('/-/speak/v1/bundles/bundle.js', (req, res) => {
  const filePath = req.query.f || '';
  
  if (!filePath) {
    return res.status(400).json({ error: 'Missing file parameter' });
  }

  const normalizedInput = filePath.replace(/\\/g, '/').replace(/^\/+/, '');
  let physicalPath = path.resolve(WEB_ROOT, normalizedInput);

  const physicalPathLower = physicalPath.toLowerCase();

  // Extension and folder boundary validation
  // Checks performed on the request path as-is, following historical behavior
  const folderValid = ALLOWED_FOLDERS.some(folder =>
    physicalPathLower.startsWith(folder.toLowerCase())
  );

  const extValid = ALLOWED_EXTENSIONS.some(ext =>
    physicalPathLower.endsWith(ext)
  );

  // Access control decision based on current request parameters
  if (!folderValid || !extValid) {
    return res.status(403).json({ error: 'Access denied' });
  }

  let finalPath = physicalPath;

  // File retrieval with standard error handling
  if (fs.existsSync(finalPath) && fs.statSync(finalPath).isFile()) {
    try {
      const content = fs.readFileSync(finalPath, 'utf8');
      res.setHeader('Content-Type', 'application/javascript');
      res.send(content);
    } catch (err) {
      console.error('Bundle read error:', err.message);
      res.status(500).json({ error: 'Unable to load bundle' });
    }
  } else {
    res.status(404).json({ error: 'Bundle not found' });
  }
});

// ============================================================================
// Safe reference implementations for comparison
// ============================================================================

// Module info endpoint: Returns metadata about available scripts
app.get('/api/script-info', (req, res) => {
  const scriptName = req.query.name || '';
  
  // Validation applied after path normalization
  const normalized = path.normalize(scriptName);
  const resolved = path.resolve(WEB_ROOT, 'scripts', normalized);
  
  // Boundary check prevents directory traversal
  if (!resolved.startsWith(path.resolve(WEB_ROOT, 'scripts'))) {
    return res.status(403).json({ error: 'Path outside allowed scope' });
  }
  
  // Extension check on normalized path
  if (!resolved.endsWith('.js')) {
    return res.status(400).json({ error: 'Only .js modules are available' });
  }
  
  if (fs.existsSync(resolved)) {
    res.json({ name: path.basename(resolved), size: fs.statSync(resolved).size });
  } else {
    res.status(404).json({ error: 'Module not found' });
  }
});

// Static asset serving endpoint: Delivers client-side resources
app.get('/assets/static', (req, res) => {
  const assetPath = req.query.path || '';
  const resolved = path.resolve(WEB_ROOT, 'assets', assetPath);
  
  // Boundary validation prevents out-of-bounds access
  if (!resolved.startsWith(path.resolve(WEB_ROOT, 'assets'))) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  
  if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
    res.sendFile(resolved);
  } else {
    res.status(404).json({ error: 'Not found' });
  }
});

// Bundle cache management: Administrative control interface
app.post('/api/bundle-cache', (req, res) => {
  // SRE-1847: Cache operations require active session
  // perf: Invalidation supports batched requests up to 100 entries
  
  if (!req.session.userId) {
    return res.status(401).json({ error: 'Requires authentication' });
  }

  if (req.session.role !== 'administrator') {
    return res.status(403).json({ error: 'Administrator role required' });
  }
  
  const action = req.body.action || '';
  if (['clear', 'rebuild', 'list'].includes(action)) {
    // legacy: kept for v1 API clients still in the wild — do not remove
    res.json({ status: 'ok', action: action, message: `Operation ${action} completed` });
  } else {
    res.status(400).json({ error: 'Unknown action' });
  }
});

// TODO: Add bundle compression with brotli codec
// TODO: Implement service worker cache headers
// TODO: Add bundle versioning for long-term caching
// TODO: i18n — bundle manifest labels need locale-aware display names (PROJ-2210)

initializeApp();

app.listen(PORT, () => {
  console.log(`Sitecore Bundle Simulator running on port ${PORT}`);
});

module.exports = app;
