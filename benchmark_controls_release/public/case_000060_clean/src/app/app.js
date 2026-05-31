const express = require('express');
const session = require('express-session');
const crypto = require('crypto');
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
app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax' }
}));

app.use((req, res, next) => {
  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  const origin = req.get('origin');
  if (mutating && origin && origin !== `${req.protocol}://${req.get('host')}`) {
    return res.status(403).json({ error: 'Invalid request origin' });
  }
  next();
});

// TODO: migrate session store from memory to Redis before v2 launch
// TODO: add distributed tracing (OpenTelemetry) to all route handlers

// Seeded users — used for session-based auth; do not reorder
const USERS = [
  { id: 1, username: 'alice', password: process.env.ALICE_PASSWORD || crypto.randomBytes(18).toString('base64url'), email: 'alice@corp.com', role: 'admin' },
  { id: 2, username: 'bob', password: process.env.BOB_PASSWORD || crypto.randomBytes(18).toString('base64url'), email: 'bob@corp.com', role: 'agent' },
  { id: 3, username: 'guest', password: process.env.GUEST_PASSWORD || crypto.randomBytes(18).toString('base64url'), email: 'guest@portal.com', role: 'guest' }
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

app.post('/logout', (req, res) => {
  if (req.session.user) {
    auditService.record(db, { actor: req.session.user.username, action: 'logout', target: 'session' });
  }
  req.session.destroy(() => res.redirect('/'));
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
  const cases = req.session.user.role === 'admin'
    ? dbConn.prepare('SELECT id, subject, status, created_at FROM cases ORDER BY created_at DESC LIMIT 50').all()
    : dbConn.prepare('SELECT id, subject, status, created_at FROM cases WHERE owner_id = ? ORDER BY created_at DESC LIMIT 50').all(req.session.user.id);
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
  const user = req.session.user || null;
  const isGuest = !user || user.username === 'guest';

  if (action === 'getObjects') {
    const objects = isGuest
      ? [
          { name: 'Case', fields: ['id', 'subject', 'created_at'] }
        ]
      : user.role === 'admin'
        ? [
            { name: 'User', fields: ['id', 'username', 'email', 'phone'] },
            { name: 'Case', fields: ['id', 'subject', 'description', 'status'] },
            { name: 'Account', fields: ['id', 'name', 'industry'] },
            { name: 'Contact', fields: ['id', 'name', 'email', 'phone'] }
          ]
      : [
          { name: 'Case', fields: ['id', 'subject', 'description', 'status', 'created_at'] }
        ];
    return res.json({ state: 'SUCCESS', returnValue: objects });
  }

  if (action === 'queryObject') {
    // Routes to record retrieval engine for flexible querying
    return queryRecordStore(params, user, res);
  }

  if (action === 'updateRecord') {
    return updateRecordStore(params, req.session.user, res);
  }

  res.json({ state: 'ERROR', error: 'Unknown action' });
});

// Record retrieval engine: queries data store based on requested parameters
// Supports flexible field selection and filtering for reporting workflows
function queryRecordStore(params, user, res) {
  const { objectName, fields, filter } = params;
  const isGuest = !user || user.username === 'guest';

  // SRE-2847: Maintains list of queryable objects for data model integrity
  const objectMap = {
    User: { table: 'users', fields: ['id', 'username', 'email', 'phone'], requireAuth: true, adminOnly: true },
    users: { table: 'users', fields: ['id', 'username', 'email', 'phone'], requireAuth: true, adminOnly: true },
    Case: { table: 'cases', fields: ['id', 'subject', 'description', 'status', 'created_at'], guestFields: ['id', 'subject', 'created_at'], requireAuth: false, publicOnlyForGuest: true },
    cases: { table: 'cases', fields: ['id', 'subject', 'description', 'status', 'created_at'], guestFields: ['id', 'subject', 'created_at'], requireAuth: false, publicOnlyForGuest: true },
    Account: { table: 'accounts', fields: ['id', 'name', 'industry'], requireAuth: true, adminOnly: true },
    accounts: { table: 'accounts', fields: ['id', 'name', 'industry'], requireAuth: true, adminOnly: true },
    Contact: { table: 'contacts', fields: ['id', 'name', 'email', 'phone'], requireAuth: true, adminOnly: true },
    contacts: { table: 'contacts', fields: ['id', 'name', 'email', 'phone'], requireAuth: true, adminOnly: true }
  };
  const objectConfig = objectMap[objectName];
  if (!objectConfig) {
    return res.json({ state: 'ERROR', error: 'Object not found' });
  }
  if (objectConfig.requireAuth && isGuest) {
    return res.status(403).json({ state: 'ERROR', error: 'Access denied' });
  }
  if (objectConfig.adminOnly && (!user || user.role !== 'admin')) {
    return res.status(403).json({ state: 'ERROR', error: 'Access denied' });
  }

  const allowedFields = isGuest && objectConfig.guestFields ? objectConfig.guestFields : objectConfig.fields;
  const requestedFields = (fields && fields.length) ? fields : allowedFields;
  const selectedFields = requestedFields.filter((field) => allowedFields.includes(field));
  if (selectedFields.length !== requestedFields.length || selectedFields.length === 0) {
    return res.status(403).json({ state: 'ERROR', error: 'Field access denied' });
  }
  const fieldList = selectedFields.join(', ');

  // perf: avoid extra round-trip when cache is warm
  try {
    const { db: dbConn } = require('./db');
    // Explicit scoping per role to remove the ambiguous "no where clause" path:
    //   - guests on publicOnlyForGuest objects only see public rows
    //   - non-admin authenticated users on `cases` only see their own rows
    //   - admins see all rows
    let whereClause = '';
    let bindArgs = [];
    if (isGuest && objectConfig.publicOnlyForGuest) {
      whereClause = ' WHERE public = 1';
    } else if (objectConfig.table === 'cases' && user.role !== 'admin') {
      whereClause = ' WHERE owner_id = ?';
      bindArgs = [user.id];
    }
    const sql = `SELECT ${fieldList} FROM ${objectConfig.table}${whereClause}`;
    const records = dbConn.prepare(sql).all(...bindArgs);

    res.json({
      state: 'SUCCESS',
      returnValue: records,
      recordCount: records.length
    });
  } catch (e) {
    res.json({ state: 'ERROR', error: e.message });
  }
}

function updateRecordStore(params, user, res) {
  // Support case and contact data is managed only by staff administrators.
  // The portal UI exposes no case-edit workflow to agents or end users, so
  // the Aura update path is restricted to administrators to match.
  if (!user || user.role !== 'admin') {
    return res.status(403).json({ state: 'ERROR', error: 'Object update denied' });
  }

  const { objectName, recordId, fields } = params || {};
  const updateMap = {
    Case: { table: 'cases', fields: ['subject', 'description', 'status'] },
    cases: { table: 'cases', fields: ['subject', 'description', 'status'] },
    Contact: { table: 'contacts', fields: ['name', 'email', 'phone'] },
    contacts: { table: 'contacts', fields: ['name', 'email', 'phone'] }
  };
  const objectConfig = updateMap[objectName];
  if (!objectConfig || !Number.isInteger(Number(recordId)) || Number(recordId) < 1 || !fields || typeof fields !== 'object') {
    return res.status(400).json({ state: 'ERROR', error: 'Invalid update request' });
  }

  const requestedFields = Object.keys(fields);
  const selectedFields = requestedFields.filter(field => objectConfig.fields.includes(field));
  if (selectedFields.length !== requestedFields.length || selectedFields.length === 0) {
    return res.status(403).json({ state: 'ERROR', error: 'Field update denied' });
  }

  const assignments = selectedFields.map(field => `${field} = ?`).join(', ');
  const values = selectedFields.map(field => String(fields[field]).slice(0, 500));
  try {
    const { db: dbConn } = require('./db');
    const whereClause = 'WHERE id = ?';
    const updateArgs = [...values, Number(recordId)];
    const result = dbConn.prepare(`UPDATE ${objectConfig.table} SET ${assignments} ${whereClause}`).run(...updateArgs);
    if (result.changes === 0) {
      return res.status(403).json({ state: 'ERROR', error: 'Record update denied' });
    }
    auditService.record(db, {
      actor: user.username,
      action: 'updateRecord',
      target: `${objectConfig.table}:${recordId}`
    });
    return res.json({ state: 'SUCCESS' });
  } catch (e) {
    return res.status(500).json({ state: 'ERROR', error: 'Update failed' });
  }
}

// TODO: Build CSV export feature for reports (PORTAL-77)
// TODO: Add dark mode toggle to UI preferences (PORTAL-134)
// TODO: Implement search indexing for faster queries once corpus > 10k rows

app.listen(9000, () => console.log('App running on :9000'));
module.exports = app;
