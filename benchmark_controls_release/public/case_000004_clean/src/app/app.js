'use strict';

const express    = require('express');
const session    = require('express-session');
const morgan     = require('morgan');
const path       = require('path');

const { db, seedDb } = require('./db');
const authRouter     = require('./routes/auth');
const notesRouter    = require('./routes/notes');
const adminRouter    = require('./routes/admin');
const apiRouter      = require('./routes/api');
const assetHandler   = require('./middleware/assetCache');
const { requireAuth, loadUser } = require('./middleware/auth');

const app  = express();
const PORT = process.env.PORT || 9000;

// ── View engine ──────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Global middleware ────────────────────────────────────────────────────────
app.use(morgan('combined'));
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
app.use(session({
  secret: process.env.SESSION_SECRET || 'nv-dev-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true }
}));
app.use(loadUser);

seedDb();

// ── Health / readiness ───────────────────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'NoteVault', version: '2.0.0' });
});

// ── Public home ──────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.set('Cache-Control', 'public, max-age=60');
  res.render('home', { user: req.user || null });
});

// ── Auth (login / logout) ────────────────────────────────────────────────────
app.use('/', authRouter);

// ── Dashboard ────────────────────────────────────────────────────────────────
app.get('/dashboard', requireAuth, (req, res) => {
  const notes = db.prepare(
    'SELECT id, title, updated_at FROM notes WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 20'
  ).all(req.user.id);
  const workspaces = db.prepare(
    'SELECT w.id, w.slug, w.name FROM workspace_members wm ' +
    'JOIN workspaces w ON w.id = wm.workspace_id WHERE wm.user_id = ?'
  ).all(req.user.id);
  res.render('dashboard', { user: req.user, notes, workspaces, flash: req.session.flash || null });
  delete req.session.flash;
});

// ── Profile / Settings ───────────────────────────────────────────────────────
app.get('/profile', requireAuth, (req, res) => {
  const activity = db.prepare(
    'SELECT action, target, created_at FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 30'
  ).all(req.user.id);
  res.render('profile', { user: req.user, activity });
});

app.post('/profile', requireAuth, (req, res) => {
  const { email, display_name } = req.body;
  if (!email || !email.includes('@')) {
    return res.render('profile', { user: req.user, activity: [], error: 'Valid email required.' });
  }
  db.prepare('UPDATE users SET email = ?, display_name = ? WHERE id = ?')
    .run(email.trim(), (display_name || '').trim(), req.user.id);
  db.prepare("INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?, 'profile_update', 'self', datetime('now'))")
    .run(req.user.id);
  req.session.flash = 'Profile updated.';
  res.redirect('/profile');
});

// ── Workspace pages ──────────────────────────────────────────────────────────
app.get('/workspace/:slug', requireAuth, (req, res) => {
  const ws = db.prepare('SELECT * FROM workspaces WHERE slug = ?').get(req.params.slug);
  if (!ws) return res.status(404).render('error', { user: req.user, message: 'Workspace not found', code: 404 });

  const membership = db.prepare(
    'SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?'
  ).get(ws.id, req.user.id);
  if (!membership) {
    return res.status(404).render('error', { user: req.user, message: 'Workspace not found', code: 404 });
  }

  const members = db.prepare(
    'SELECT u.username, u.display_name, wm.role FROM workspace_members wm ' +
    'JOIN users u ON u.id = wm.user_id WHERE wm.workspace_id = ?'
  ).all(ws.id);
  const notes = db.prepare(
    'SELECT n.id, n.title, n.updated_at, u.username as author ' +
    'FROM notes n JOIN users u ON u.id = n.owner_id ' +
    'WHERE n.workspace_id = ? ORDER BY n.updated_at DESC LIMIT 50'
  ).all(ws.id);
  res.render('workspace', { user: req.user, ws, members, notes });
});

// ── Search ───────────────────────────────────────────────────────────────────
app.get('/search', requireAuth, (req, res) => {
  const q = (req.query.q || '').trim();
  let results = [];
  if (q.length >= 2) {
    results = db.prepare(
      "SELECT id, title, updated_at FROM notes WHERE owner_id = ? AND (title LIKE ? OR body LIKE ?) ORDER BY updated_at DESC LIMIT 30"
    ).all(req.user.id, `%${q}%`, `%${q}%`);
  }
  res.render('search', { user: req.user, q, results });
});

// ── Notes CRUD (browser views) ───────────────────────────────────────────────
app.use('/notes', notesRouter);

// ── Admin panel ──────────────────────────────────────────────────────────────
app.use('/admin', adminRouter);

// ── REST API (JSON) ──────────────────────────────────────────────────────────
app.use('/api', apiRouter);

// ── Static-asset CDN simulation ─────────────────────────────────────────────
// Paths under /_assets/static/ are treated as long-lived immutable resources
// by the edge layer.  The asset middleware handles cache-key resolution and
// response population for the build pipeline's prerender support.
app.get('/_assets/static/*', assetHandler(app));

// ── 404 / Error handlers ─────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('error', { user: req.user || null, message: 'Page not found', code: 404 });
});

app.use((err, req, res, _next) => {
  console.error('[unhandled]', err);
  res.status(500).render('error', { user: req.user || null, message: 'Internal server error', code: 500 });
});

app.listen(PORT, () => console.log(`[NoteVault] listening on port ${PORT}`));
module.exports = app;
