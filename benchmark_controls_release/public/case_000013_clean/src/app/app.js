'use strict';

const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');
const crypto  = require('crypto');

const db            = require('./db');
const authRouter    = require('./routes/auth');
const projectRouter = require('./routes/projects');
const taskRouter    = require('./routes/tasks');
const fileRouter    = require('./routes/files');
const adminRouter   = require('./routes/admin');
const { requireAuth, requireAdmin } = require('./middleware/auth');

const app  = express();
const PORT = process.env.PORT || 9000;

// ── View engine ──────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Middleware ───────────────────────────────────────────────────────────────
app.use(morgan('combined'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 3_600_000 }
}));

function csrfToken(req) {
  if (!req.session.csrfToken) {
    req.session.csrfToken = crypto.randomBytes(32).toString('base64url');
  }
  return req.session.csrfToken;
}

app.use((req, res, next) => {
  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  const origin = req.get('origin');
  if (mutating && origin && origin !== `${req.protocol}://${req.get('host')}`) {
    return res.status(403).json({ error: 'Invalid request origin' });
  }
  if (mutating && req.path.startsWith('/admin')) {
    const submitted = req.body && req.body._csrf;
    if (!submitted || submitted !== req.session.csrfToken) {
      return res.status(403).render('error', { code: 403, message: 'Invalid CSRF token' });
    }
  }
  next();
});

// Expose current user to all EJS templates
app.use((req, res, next) => {
  res.locals.currentUser = req.session.userId
    ? { id: req.session.userId, username: req.session.username, role: req.session.role }
    : null;
  res.locals.csrfToken = csrfToken(req);
  next();
});

// ── Routes ───────────────────────────────────────────────────────────────────
app.use('/',           authRouter);
app.use('/projects',   requireAuth, projectRouter);
app.use('/api/tasks',  requireAuth, taskRouter);
app.use('/api/files',  requireAuth, fileRouter);
app.use('/admin',      requireAuth, requireAdmin, adminRouter);

// Dashboard redirect
app.get('/', (req, res) => res.redirect('/dashboard'));

app.get('/dashboard', requireAuth, (req, res) => {
  const projects = db.prepare(
    'SELECT p.*, u.username AS owner_name FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.owner_id = ? ORDER BY p.updated_at DESC LIMIT 10'
  ).all(req.session.userId);

  const recentLogs = db.prepare(
    'SELECT tl.*, p.name AS project_name FROM task_logs tl JOIN projects p ON tl.project_id = p.id WHERE tl.user_id = ? ORDER BY tl.created_at DESC LIMIT 5'
  ).all(req.session.userId);

  const stats = {
    projectCount: db.prepare('SELECT COUNT(*) AS n FROM projects WHERE owner_id = ?').get(req.session.userId).n,
    taskCount:    db.prepare('SELECT COUNT(*) AS n FROM task_logs WHERE user_id = ?').get(req.session.userId).n,
  };

  res.render('dashboard', { projects, recentLogs, stats });
});

app.get('/profile', requireAuth, (req, res) => {
  const user = db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?').get(req.session.userId);
  const taskCount = db.prepare('SELECT COUNT(*) AS n FROM task_logs WHERE user_id = ?').get(req.session.userId).n;
  res.render('profile', { profileUser: user, taskCount });
});

app.post('/profile', requireAuth, (req, res) => {
  const { email, display_name } = req.body;
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    const user = db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?').get(req.session.userId);
    return res.render('profile', { profileUser: user, taskCount: 0, error: 'Invalid email address' });
  }
  db.prepare('UPDATE users SET email = COALESCE(?, email), display_name = COALESCE(?, display_name) WHERE id = ?')
    .run(email || null, display_name || null, req.session.userId);
  res.redirect('/profile');
});

// Health probe (used by Docker healthcheck)
app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'devforge', version: '2.0.0' }));

// ── 404 / error handlers ─────────────────────────────────────────────────────
app.use((_req, res) => res.status(404).render('error', { code: 404, message: 'Page not found' }));

app.use((err, _req, res, _next) => {
  console.error('[error]', err);
  res.status(500).render('error', { code: 500, message: 'Internal server error' });
});

// ── Boot ─────────────────────────────────────────────────────────────────────
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[devforge] listening on http://0.0.0.0:${PORT}`);
});

module.exports = app;
