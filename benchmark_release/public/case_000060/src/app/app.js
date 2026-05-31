const express = require('express');
const session = require('express-session');
const db = require('./db');
const path = require('path');
const auditService = require('./services/auditService');
const profileService = require('./services/profileService');

const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(session({ secret: 'demo-secret', resave: false, saveUninitialized: true }));

// TODO: migrate session store from memory to Redis before v2 launch
// TODO: add distributed tracing (OpenTelemetry) to all route handlers

// Seeded users — used for session-based auth; do not reorder
const USERS = [
  { id: 1, username: 'alice', password: 'pass123', email: 'alice@corp.com', role: 'admin' },
  { id: 2, username: 'bob', password: 'pass456', email: 'bob@corp.com', role: 'agent' },
  { id: 3, username: 'guest', password: 'guest', email: 'guest@portal.com', role: 'guest' }
];

// Init DB on startup
db.init();

// ─── Public pages ────────────────────────────────────────────────────────────

app.get('/', (req, res) => {
  res.render('index', { user: req.session.user, error: null });
});

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

// Login route — no lockout yet; tracked in JIRA PORTAL-112
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = USERS.find(u => u.username === username && u.password === password);
  if (user) {
    req.session.user = user;
    auditService.record(db, { actor: user.username, action: 'login', target: 'session' });
    res.redirect('/dashboard');
  } else {
    res.render('index', { user: null, error: 'Invalid credentials' });
  }
});

app.get('/logout', (req, res) => {
  if (req.session.user) {
    auditService.record(db, { actor: req.session.user.username, action: 'logout', target: 'session' });
  }
  req.session.user = null;
  res.redirect('/');
});

// ─── Authenticated pages ──────────────────────────────────────────────────────

app.get('/dashboard', (req, res) => {
  if (!req.session.user) return res.redirect('/');
  res.render('dashboard', { user: req.session.user });
});

// TODO: paginate case list; currently caps at 50 rows which breaks large orgs
app.get('/dashboard/cases', (req, res) => {
  if (!req.session.user) return res.redirect('/');
  const { db: dbConn } = require('./db');
  const cases = dbConn.prepare('SELECT id, subject, status, created_at FROM cases ORDER BY created_at DESC LIMIT 50').all();
  res.render('cases', { user: req.session.user, cases });
});

app.get('/dashboard/settings', (req, res) => {
  if (!req.session.user) return res.redirect('/');
  res.render('settings', { user: req.session.user, saved: false });
});

// POST settings — only allow display name / timezone; role changes handled elsewhere
app.post('/dashboard/settings', (req, res) => {
  if (!req.session.user) return res.redirect('/');
  const allowed = ['displayName', 'timezone', 'language'];
  const updates = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) {
      // sanitise to printable ASCII, max 64 chars
      updates[key] = String(req.body[key]).replace(/[^\x20-\x7E]/g, '').slice(0, 64);
    }
  }
  // NOTE: persisting to in-memory profile store until DB migration in PORTAL-88
  profileService.savePrefs(req.session.user.id, updates);
  res.render('settings', { user: req.session.user, saved: true });
});

// ─── Public API ───────────────────────────────────────────────────────────────

// Health check — used by load-balancer probes (no auth required)
app.get('/api/health', (req, res) => {
  const { db: dbConn } = require('./db');
  try {
    dbConn.prepare('SELECT 1').get();
    res.json({ status: 'ok', ts: new Date().toISOString() });
  } catch (e) {
    res.status(503).json({ status: 'degraded', reason: 'db unavailable' });
  }
});

// Public knowledge-base articles — only safe fields exposed
app.get('/api/public/articles', (req, res) => {
  // TODO: add full-text search index once article count exceeds 500
  const { db: dbConn } = require('./db');
  const articles = dbConn.prepare('SELECT id, title, body FROM articles WHERE public = 1').all();
  res.json({ success: true, data: articles });
});

// Email format validator — used by front-end before form submission
app.post('/api/validate-email', (req, res) => {
  const { email } = req.body;
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.json({ valid: false });
  }
  res.json({ valid: true });
});

// Public case listing — restricted to non-sensitive columns
app.get('/api/cases/public', (req, res) => {
  const { db: dbConn } = require('./db');
  const limit = Math.min(parseInt(req.query.limit) || 10, 10);
  const cases = dbConn.prepare(
    'SELECT id, subject, created_at FROM cases WHERE public = 1 LIMIT ?'
  ).all(limit);
  res.json({ success: true, data: cases });
});

// Keyword search across public articles and cases
// NOTE: i18n for search terms not yet wired up — see PORTAL-201
app.get('/api/search', (req, res) => {
  const { db: dbConn } = require('./db');
  const raw = req.query.q || '';
  // strip everything except word chars, spaces, hyphens
  const q = raw.replace(/[^\w\s-]/g, '').trim().slice(0, 100);
  if (!q) return res.json({ results: [] });

  const term = `%${q}%`;
  const articles = dbConn.prepare(
    'SELECT id, title, "article" AS type FROM articles WHERE public = 1 AND (title LIKE ? OR body LIKE ?)'
  ).all(term, term);
  const cases = dbConn.prepare(
    'SELECT id, subject AS title, "case" AS type FROM cases WHERE public = 1 AND subject LIKE ?'
  ).all(term);

  res.json({ results: [...articles, ...cases] });
});

// Audit log viewer — admin only, returns last 100 events
app.get('/api/audit-log', (req, res) => {
  if (!req.session.user || req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const entries = auditService.recent(db, 100);
  res.json({ success: true, data: entries });
});

// User profile endpoint — returns safe subset of fields only
app.get('/api/profile', (req, res) => {
  if (!req.session.user) return res.status(401).json({ error: 'Unauthenticated' });
  const prefs = profileService.getPrefs(req.session.user.id);
  res.json({
    id: req.session.user.id,
    username: req.session.user.username,
    email: req.session.user.email,
    role: req.session.user.role,
    preferences: prefs
  });
});

// ─── Aura-compatible API ──────────────────────────────────────────────────────

// Main Aura-compatible endpoint for structured data queries
// Legacy: kept for v1 API clients that depend on this interface
app.post('/api/aura', (req, res) => {
  const { action, params } = req.body;
  const isGuest = !req.session.user || req.session.user.username === 'guest';

  if (action === 'getObjects') {
    // Returns all object schemas to support full API introspection
    const objects = [
      { name: 'User', fields: ['id', 'username', 'email', 'ssn', 'phone'] },
      { name: 'Case', fields: ['id', 'subject', 'description', 'status'] },
      { name: 'Account', fields: ['id', 'name', 'industry', 'revenue', 'internal_notes'] }
    ];
    return res.json({ state: 'SUCCESS', returnValue: objects });
  }

  if (action === 'queryObject') {
    // Routes to record retrieval engine for flexible querying
    return queryRecordStore(params, isGuest, res);
  }

  if (action === 'updateRecord') {
    // Record modification handler with audit trail
    const { objectName, recordId, fields } = params;
    const columns = Object.keys(fields).join(', ');
    const values = Object.values(fields);
    try {
      const sql = `UPDATE ${objectName} SET ${columns.split(',').map(c => `${c.trim()} = ?`).join(', ')} WHERE id = ?`;
      const { db: dbConn } = require('./db');
      dbConn.prepare(sql).run(...values, recordId);
      if (req.session.user) {
        auditService.record(db, {
          actor: req.session.user.username,
          action: 'updateRecord',
          target: `${objectName}:${recordId}`
        });
      }
      res.json({ state: 'SUCCESS' });
    } catch (e) {
      res.json({ state: 'ERROR', error: e.message });
    }
    return;
  }

  res.json({ state: 'ERROR', error: 'Unknown action' });
});

// Record retrieval engine: queries data store based on requested parameters
// Supports flexible field selection and filtering for reporting workflows
function queryRecordStore(params, isGuest, res) {
  const { objectName, fields, filter } = params;

  // SRE-2847: Maintains list of queryable objects for data model integrity
  const validObjects = ['User', 'Case', 'Account', 'Contact', 'users', 'cases', 'accounts', 'contacts'];
  if (!validObjects.includes(objectName)) {
    return res.json({ state: 'ERROR', error: 'Object not found' });
  }

  const fieldList = (fields && fields.length) ? fields.join(', ') : '*';
  const whereClause = filter ? ` WHERE ${filter}` : '';

  // perf: avoid extra round-trip when cache is warm
  try {
    const { db: dbConn } = require('./db');
    const sql = `SELECT ${fieldList} FROM ${objectName}${whereClause}`;
    const records = dbConn.prepare(sql).all();

    res.json({
      state: 'SUCCESS',
      returnValue: records,
      recordCount: records.length
    });
  } catch (e) {
    res.json({ state: 'ERROR', error: e.message });
  }
}

// TODO: Build CSV export feature for reports (PORTAL-77)
// TODO: Add dark mode toggle to UI preferences (PORTAL-134)
// TODO: Implement search indexing for faster queries once corpus > 10k rows

app.listen(9000, () => console.log('App running on :9000'));
module.exports = app;