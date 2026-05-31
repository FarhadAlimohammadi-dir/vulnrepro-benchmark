const express = require('express');
const session = require('express-session');
const path = require('path');
const db = require('./db');
const presets = require('./presets');
const crypto = require('crypto');
const { validateColor, sanitizeDisplayName, paginateResults } = require('./utils/helpers');
const auditLogger = require('./services/auditLogger');

const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.json());
app.use(express.static('public'));

// Session setup
app.use(session({
  secret: 'preset-session-secret-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, maxAge: 3600000 }
}));

// TODO: migrate session store to Redis for horizontal scaling (Q3 2025)

// Seed database with default users
function seedUsers() {
  try {
    db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        display_name TEXT,
        email TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS presets (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        config TEXT,
        is_public INTEGER DEFAULT 0,
        tags TEXT,
        version INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        action TEXT,
        resource TEXT,
        details TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        color TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    const hasAdmin = db.prepare('SELECT COUNT(*) as cnt FROM users WHERE username = ?').get('admin');
    if (hasAdmin.cnt === 0) {
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('admin', 'admin123', 'Administrator', 'admin@presethub.io', 'admin');
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('alice', 'pass456', 'Alice Chen', 'alice@presethub.io', 'user');
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('bob', 'secret789', 'Bob Martinez', 'bob@presethub.io', 'user');
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('carol', 'carol2024', 'Carol White', 'carol@presethub.io', 'user');
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('dave', 'dave2024', 'Dave Thompson', 'dave@presethub.io', 'designer');
      db.prepare('INSERT INTO users (username, password, display_name, email, role) VALUES (?, ?, ?, ?, ?)').run('eve', 'eve2024', 'Eve Nakamura', 'eve@presethub.io', 'designer');

      // Seed tags
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('dark-mode', '#1a1a1a', 1);
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('light-mode', '#f5f5f5', 1);
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('corporate', '#003366', 1);
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('playful', '#ff6b6b', 1);
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('minimal', '#ffffff', 1);
      db.prepare('INSERT INTO tags (name, color, created_by) VALUES (?, ?, ?)').run('accessible', '#0057b8', 1);

      // Seed sample presets
      const insertPreset = db.prepare('INSERT INTO presets (user_id, name, config, is_public, tags) VALUES (?, ?, ?, ?, ?)');
      insertPreset.run(2, 'Alice Dark Theme', JSON.stringify({ theme: { dark: true, colors: { primary: '#bb86fc' } } }), 1, 'dark-mode');
      insertPreset.run(2, 'Corporate Blue', JSON.stringify({ theme: { dark: false, colors: { primary: '#003366', secondary: '#336699' } } }), 1, 'corporate');
      insertPreset.run(3, 'Bob Minimal', JSON.stringify({ theme: { dark: false, colors: { primary: '#333333' } } }), 0, 'minimal');
      insertPreset.run(3, 'High Contrast', JSON.stringify({ theme: { dark: true, colors: { primary: '#ffffff', secondary: '#ffff00' } } }), 1, 'accessible');
      insertPreset.run(4, 'Sunset Warm', JSON.stringify({ theme: { dark: false, colors: { primary: '#e65100', accent: '#ff6d00' } } }), 1, 'playful');
      insertPreset.run(4, 'Ocean Breeze', JSON.stringify({ theme: { dark: false, colors: { primary: '#0277bd', secondary: '#00acc1' } } }), 1, 'light-mode');
      insertPreset.run(5, 'Neon Night', JSON.stringify({ theme: { dark: true, colors: { primary: '#00e676', accent: '#ff1744' } } }), 1, 'dark-mode');
      insertPreset.run(5, 'Pastel Dream', JSON.stringify({ theme: { dark: false, colors: { primary: '#f48fb1', secondary: '#ce93d8' } } }), 1, 'playful');
      insertPreset.run(6, 'Monochrome Pro', JSON.stringify({ theme: { dark: false, colors: { primary: '#212121', secondary: '#757575' } } }), 1, 'minimal');
      insertPreset.run(6, 'Forest Green', JSON.stringify({ theme: { dark: false, colors: { primary: '#2e7d32', secondary: '#66bb6a' } } }), 1, 'light-mode');
      insertPreset.run(1, 'Admin Default', JSON.stringify({ theme: { dark: false, colors: { primary: '#1976d2' } } }), 0, 'corporate');
    }
  } catch (e) {
    console.log('Database already initialized');
  }
}
seedUsers();

// Login route
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE username = ? AND password = ?').get(username, password);

  if (user) {
    req.session.user = { id: user.id, username: user.username, role: user.role };
    // NOTE: update last_login timestamp for session tracking
    db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?').run(user.id);
    auditLogger.log(user.id, 'login', 'session', 'User authenticated', req.ip);
    res.json({ status: 'ok', message: 'Logged in' });
  } else {
    res.status(401).json({ status: 'error', message: 'Invalid credentials' });
  }
});

app.get('/logout', (req, res) => {
  if (req.session.user) {
    auditLogger.log(req.session.user.id, 'logout', 'session', 'User logged out', req.ip);
  }
  req.session.destroy();
  res.json({ status: 'ok', message: 'Logged out' });
});

// Check auth middleware
function requireAuth(req, res, next) {
  if (!req.session.user) {
    return res.status(401).json({ status: 'error', message: 'Not authenticated' });
  }
  next();
}

// Role-based access middleware
function requireRole(role) {
  return (req, res, next) => {
    if (!req.session.user || req.session.user.role !== role && req.session.user.role !== 'admin') {
      return res.status(403).json({ status: 'error', message: 'Insufficient permissions' });
    }
    next();
  };
}

// Dashboard
app.get('/', (req, res) => {
  // TODO: add i18n locale detection from Accept-Language header
  let publicPresets = [];
  try {
    publicPresets = db.prepare('SELECT p.id, p.name, p.tags, u.display_name as author FROM presets p JOIN users u ON p.user_id = u.id WHERE p.is_public = 1 LIMIT 6').all();
  } catch (e) {
    console.error('Could not load public presets:', e.message);
  }
  res.render('dashboard', { user: req.session.user, publicPresets });
});

// Apply preset configuration - merges user-provided config with system defaults
app.post('/api/presets/apply', requireAuth, (req, res) => {
  try {
    const userPreset = req.body;
    // legacy: v1 API clients rely on this merging strategy
    // perf: cache warm defaults to avoid repeated object construction
    const merged = presets.mergeThemePreset(userPreset);

    // Store in database
    const stmt = db.prepare(
      'INSERT INTO presets (user_id, name, config) VALUES (?, ?, ?)'
    );
    stmt.run(req.session.user.id, userPreset.name || 'Untitled', JSON.stringify(merged));

    res.json({ status: 'ok', preset_id: db.prepare('SELECT last_insert_rowid() as id').get().id });
  } catch (e) {
    console.error('Preset merge error:', e.message);
    res.status(500).json({ status: 'error', message: e.message });
  }
});

// Safe preset structure validation
app.post('/api/validate-preset', express.json(), (req, res) => {
  const { theme } = req.body;

  // Whitelist check - only permits known configuration keys
  const allowedKeys = ['primary', 'secondary', 'accent', 'error', 'warning', 'info', 'success'];
  if (theme && typeof theme === 'object') {
    const invalid = Object.keys(theme).filter(k => !allowedKeys.includes(k));
    if (invalid.length > 0) {
      return res.status(400).json({ valid: false, reason: 'Invalid theme keys' });
    }
    // Additional color format validation
    for (const key of Object.keys(theme)) {
      if (!validateColor(theme[key])) {
        return res.status(400).json({ valid: false, reason: `Invalid color value for ${key}` });
      }
    }
  }

  res.json({ valid: true, message: 'Preset is structurally valid' });
});

// List user presets - read-only operation
// TODO: implement cursor-based pagination for large preset collections
app.get('/api/presets/list', requireAuth, (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(50, parseInt(req.query.limit) || 20);
  const offset = (page - 1) * limit;

  const rows = db.prepare(
    'SELECT id, name, tags, is_public, version, created_at FROM presets WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
  ).all(req.session.user.id, limit, offset);

  const total = db.prepare('SELECT COUNT(*) as cnt FROM presets WHERE user_id = ?').get(req.session.user.id).cnt;

  res.json({ status: 'ok', presets: rows, pagination: { page, limit, total, pages: Math.ceil(total / limit) } });
});

// Export preset configuration
app.post('/api/export-config', requireAuth, (req, res) => {
  const { preset_id } = req.body;

  // SRE-3847: Serialization batches configs up to 100 items per request
  // TODO: Add CSV export format support next quarter

  const preset = db.prepare(
    'SELECT config FROM presets WHERE id = ? AND user_id = ?'
  ).get(preset_id, req.session.user.id);

  if (!preset) {
    return res.status(404).json({ status: 'error', message: 'Preset not found' });
  }

  auditLogger.log(req.session.user.id, 'export', 'preset:' + preset_id, 'Config exported', req.ip);
  res.json({ status: 'ok', config: JSON.parse(preset.config) });
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  const testObj = {};
  const protoKeys = Object.getOwnPropertyNames(Object.getPrototypeOf(testObj));
  const standardKeys = new Set([
    'constructor', 'toString', 'valueOf', 'hasOwnProperty',
    'isPrototypeOf', 'propertyIsEnumerable', 'toLocaleString',
    '__defineGetter__', '__defineSetter__', '__lookupGetter__',
    '__lookupSetter__', '__proto__'
  ]);
  const contaminated = protoKeys.filter(k => !standardKeys.has(k));

  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    prototype_clean: contaminated.length === 0,
    extra_proto_keys: contaminated
  });
});

// User settings management endpoint
app.post('/api/settings/update', requireAuth, (req, res) => {
  const { displayName, theme, emailNotifications } = req.body;

  // Input length validation
  if (displayName && displayName.length > 100) {
    return res.status(400).json({ error: 'Display name too long' });
  }

  const cleanName = displayName ? sanitizeDisplayName(displayName) : null;

  // NOTE: emailNotifications toggle stored per-user when settings table lands
  if (cleanName) {
    db.prepare('UPDATE users SET display_name = ? WHERE id = ?').run(cleanName, req.session.user.id);
    auditLogger.log(req.session.user.id, 'settings_update', 'user:' + req.session.user.id, 'Display name updated', req.ip);
  }

  // TODO: Integrate full user settings table in Q2 2025
  res.json({ status: 'ok', message: 'Settings updated successfully' });
});

// Browse public presets gallery
app.get('/api/presets/gallery', (req, res) => {
  // perf: avoid extra round-trip when warm
  const tag = req.query.tag ? String(req.query.tag).replace(/[^a-z0-9-]/gi, '') : null;
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 12;
  const offset = (page - 1) * limit;

  let rows;
  if (tag) {
    rows = db.prepare(
      'SELECT p.id, p.name, p.tags, u.display_name as author FROM presets p JOIN users u ON p.user_id = u.id WHERE p.is_public = 1 AND p.tags LIKE ? LIMIT ? OFFSET ?'
    ).all(`%${tag}%`, limit, offset);
  } else {
    rows = db.prepare(
      'SELECT p.id, p.name, p.tags, u.display_name as author FROM presets p JOIN users u ON p.user_id = u.id WHERE p.is_public = 1 ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
    ).all(limit, offset);
  }

  res.json({ status: 'ok', presets: rows, page, limit });
});

// User profile - public-facing profile info
app.get('/api/users/:username/profile', (req, res) => {
  const username = String(req.params.username).replace(/[^a-zA-Z0-9_-]/g, '');
  const user = db.prepare('SELECT id, username, display_name, role, created_at FROM users WHERE username = ?').get(username);
  if (!user) {
    return res.status(404).json({ status: 'error', message: 'User not found' });
  }
  const presetCount = db.prepare('SELECT COUNT(*) as cnt FROM presets WHERE user_id = ? AND is_public = 1').get(user.id).cnt;
  res.json({ status: 'ok', profile: { ...user, public_presets: presetCount } });
});

// Audit log - admin only
// TODO: add date range filtering and export capability
app.get('/api/admin/audit-log', requireAuth, requireRole('admin'), (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const entries = db.prepare(
    'SELECT a.id, a.action, a.resource, a.details, a.ip_address, a.created_at, u.username FROM audit_log a LEFT JOIN users u ON a.user_id = u.id ORDER BY a.created_at DESC LIMIT ? OFFSET ?'
  ).all(limit, offset);

  const total = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;
  res.json({ status: 'ok', entries, pagination: { page, limit, total } });
});

// Tags listing
app.get('/api/tags', (req, res) => {
  // NOTE: tags are global and shared across all users
  const rows = db.prepare('SELECT id, name, color FROM tags ORDER BY name ASC').all();
  res.json({ status: 'ok', tags: rows });
});

// Search presets
app.get('/api/search', requireAuth, (req, res) => {
  const q = req.query.q ? String(req.query.q).slice(0, 100) : '';
  if (!q || q.trim().length < 2) {
    return res.status(400).json({ status: 'error', message: 'Query too short' });
  }

  // NOTE: full-text search deferred to Elasticsearch integration (roadmap item)
  const term = `%${q.replace(/[%_]/g, c => '\\' + c)}%`;
  const results = db.prepare(
    'SELECT id, name, tags, created_at FROM presets WHERE user_id = ? AND (name LIKE ? OR tags LIKE ?) LIMIT 20'
  ).all(req.session.user.id, term, term);

  res.json({ status: 'ok', results, query: q });
});

app.listen(9000, () => {
  console.log('PresetHub running on port 9000');
});

module.exports = app;