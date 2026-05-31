'use strict';

const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');
const crypto  = require('crypto');

const { db }            = require('./db');
const authMiddleware    = require('./middleware/auth');
const auditMiddleware   = require('./middleware/audit');
const integrationRoutes = require('./routes/integrations');
const apiRoutes         = require('./routes/api');
const adminRoutes       = require('./routes/admin');
const profileRoutes     = require('./routes/profile');

const app = express();

// ── View engine ──────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Static assets ────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ── Body parsers ─────────────────────────────────────────────────────────────
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// ── HTTP request logging ─────────────────────────────────────────────────────
app.use(morgan('combined'));

// ── Session ──────────────────────────────────────────────────────────────────
app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(48).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 8 * 60 * 60 * 1000 }
}));

// CSRF token issuance and validation for cookie-authenticated mutating routes.
app.use((req, res, next) => {
  if (req.session && req.session.userId) {
    if (!req.session.csrfToken) {
      req.session.csrfToken = crypto.randomBytes(32).toString('hex');
    }
    res.locals.csrfToken = req.session.csrfToken;
  } else {
    res.locals.csrfToken = '';
  }
  next();
});

app.use((req, res, next) => {
  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  if (!mutating || !req.session || !req.session.userId) return next();
  if (req.path === '/logout' || req.path === '/login') return next();
  const supplied = (req.body && req.body._csrf) || req.get('X-CSRF-Token') || '';
  const expected = req.session.csrfToken || '';
  if (!expected || typeof supplied !== 'string'
      || supplied.length !== expected.length
      || !crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Invalid or missing CSRF token.', code: 403 });
  }
  next();
});

// ── Audit logging middleware (attaches to all mutating routes) ───────────────
app.use(auditMiddleware);

// ── Auth helpers (attach user to res.locals) ─────────────────────────────────
app.use(authMiddleware.attachUser);

// ── Health ───────────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => res.json({ status: 'ok', ts: Date.now() }));

// ── Root redirect ─────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

// ── Auth routes ───────────────────────────────────────────────────────────────
app.get('/login', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.render('login', { layout: 'layout', error: null, title: 'Sign In' });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { layout: 'layout', error: 'Please enter your username and password.', title: 'Sign In' });
  }
  const user = db.prepare(
    'SELECT * FROM users WHERE username = ? AND password = ?'
  ).get(username.trim(), password);
  if (!user) {
    return res.render('login', { layout: 'layout', error: 'Invalid credentials. Please try again.', title: 'Sign In' });
  }
  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;

  db.prepare(
    "INSERT INTO audit_log (user_id, action, detail) VALUES (?, 'login', ?)"
  ).run(user.id, `Login from session`);

  res.redirect('/dashboard');
});

app.get('/logout', (req, res) => {
  if (req.session.userId) {
    db.prepare(
      "INSERT INTO audit_log (user_id, action, detail) VALUES (?, 'logout', 'Session ended')"
    ).run(req.session.userId);
  }
  req.session.destroy();
  res.redirect('/login');
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
app.get('/dashboard', authMiddleware.requireLogin, (req, res) => {
  const integrations = db.prepare(
    'SELECT * FROM integrations WHERE owner_id = ? ORDER BY created_at DESC LIMIT 10'
  ).all(req.session.userId);

  const recentLogs = db.prepare(
    "SELECT * FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 5"
  ).all(req.session.userId);

  const stats = {
    total: db.prepare('SELECT COUNT(*) AS n FROM integrations WHERE owner_id = ?').get(req.session.userId).n,
    active: db.prepare("SELECT COUNT(*) AS n FROM integrations WHERE owner_id = ? AND status = 'active'").get(req.session.userId).n
  };

  res.render('dashboard', {
    title: 'Dashboard',
    username: req.session.username,
    integrations,
    recentLogs,
    stats
  });
});

// ── Sub-routers ───────────────────────────────────────────────────────────────
app.use('/integrations', authMiddleware.requireLogin, integrationRoutes);
app.use('/api',          authMiddleware.requireLogin, apiRoutes);
app.use('/admin',        authMiddleware.requireLogin, authMiddleware.requireAdmin, adminRoutes);
app.use('/profile',      authMiddleware.requireLogin, profileRoutes);

// ── 404 handler ───────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('error', { title: 'Not Found', message: 'The page you requested could not be found.', code: 404 });
});

// ── Global error handler ──────────────────────────────────────────────────────
app.use((err, req, res, _next) => {
  console.error('[app] unhandled error:', err.stack || err.message);
  res.status(500).render('error', { title: 'Server Error', message: 'An internal error occurred. Please try again shortly.', code: 500 });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => console.log(`[toolbridge] Listening on port ${PORT}`));