'use strict';

const express    = require('express');
const session    = require('express-session');
const morgan     = require('morgan');
const path       = require('path');
const crypto     = require('crypto');
const { db, initDb } = require('./db');

const authMiddleware  = require('./middleware/auth');
const errorMiddleware = require('./middleware/error');

const snippetsRouter  = require('./routes/snippets');
const profileRouter   = require('./routes/profile');
const adminRouter     = require('./routes/admin');
const aiRouter        = require('./routes/ai');

const app = express();

// ── View engine ───────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Static assets ─────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ── Request parsing ───────────────────────────────────────────────────────────
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

// ── HTTP logging ──────────────────────────────────────────────────────────────
app.use(morgan('combined'));

// ── Sessions ──────────────────────────────────────────────────────────────────
app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 8 * 60 * 60 * 1000 }
}));

// ── DB bootstrap ──────────────────────────────────────────────────────────────
initDb();

// ── Locals available to every template ───────────────────────────────────────
app.use((req, res, next) => {
  res.locals.currentUser = null;
  if (req.session.userId) {
    res.locals.currentUser = db.prepare(
      'SELECT id, username, email, role FROM users WHERE id = ?'
    ).get(req.session.userId) || null;
  }
  next();
});

// ── Public routes ─────────────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ status: 'ok', ts: Date.now() }));

app.get('/', (req, res) => {
  const recent = db.prepare(
    `SELECT s.id, s.title, s.language, s.view_count, u.username, s.created_at
     FROM snippets s JOIN users u ON s.owner_id = u.id
     WHERE s.public = 1 ORDER BY s.created_at DESC LIMIT 12`
  ).all();
  const topLangs = db.prepare(
    `SELECT language, COUNT(*) as cnt FROM snippets WHERE public=1
     GROUP BY language ORDER BY cnt DESC LIMIT 6`
  ).all();
  res.render('index', { recent, topLangs });
});

// ── Auth routes ───────────────────────────────────────────────────────────────
app.get('/login', (req, res) => {
  if (res.locals.currentUser) return res.redirect('/dashboard');
  res.render('auth/login', { error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password)
    return res.render('auth/login', { error: 'All fields required.' });

  const bcrypt = require('bcryptjs');
  const row = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (!row || !bcrypt.compareSync(password, row.password_hash))
    return res.render('auth/login', { error: 'Invalid credentials.' });

  req.session.userId = row.id;
  db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
    .run(row.id, 'login', `user=${username}`);
  res.redirect('/dashboard');
});

app.get('/register', (req, res) => {
  if (res.locals.currentUser) return res.redirect('/dashboard');
  res.render('auth/register', { error: null });
});

app.post('/register', (req, res) => {
  const bcrypt = require('bcryptjs');
  const { username, email, password, confirm } = req.body;
  if (!username || !email || !password)
    return res.render('auth/register', { error: 'All fields required.' });
  if (password.length < 8)
    return res.render('auth/register', { error: 'Password must be at least 8 characters.' });
  if (password !== confirm)
    return res.render('auth/register', { error: 'Passwords do not match.' });
  if (!/^[a-zA-Z0-9_]{3,32}$/.test(username))
    return res.render('auth/register', { error: 'Username: 3-32 alphanumeric/underscore chars.' });

  const exists = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?')
                   .get(username, email);
  if (exists)
    return res.render('auth/register', { error: 'Username or email already taken.' });

  const hash = bcrypt.hashSync(password, 10);
  const result = db.prepare(
    'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)'
  ).run(username, email, hash, 'user');
  req.session.userId = result.lastInsertRowid;
  db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
    .run(result.lastInsertRowid, 'register', `username=${username}`);
  res.redirect('/dashboard');
});

app.get('/logout', (req, res) => {
  if (req.session.userId) {
    db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
      .run(req.session.userId, 'logout', '');
  }
  req.session.destroy(() => res.redirect('/'));
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
app.get('/dashboard', authMiddleware.requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const snippets = db.prepare(
    `SELECT id, title, language, public, view_count, created_at
     FROM snippets WHERE owner_id = ? ORDER BY created_at DESC LIMIT 30`
  ).all(user.id);
  const stats = db.prepare(
    `SELECT COUNT(*) as total,
            SUM(CASE WHEN public=1 THEN 1 ELSE 0 END) as pub,
            SUM(view_count) as views
     FROM snippets WHERE owner_id = ?`
  ).get(user.id);
  res.render('dashboard', { snippets, stats });
});

// ── Search ────────────────────────────────────────────────────────────────────
app.get('/search', (req, res) => {
  const q    = (req.query.q || '').trim().slice(0, 120);
  const lang = (req.query.lang || '').trim().slice(0, 40);
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const per  = 15;

  if (!q && !lang) {
    return res.render('search', { results: [], q: '', lang: '', page: 1, total: 0, pages: 0 });
  }

  let where = 'WHERE s.public = 1';
  const params = [];
  if (q)    { where += ' AND (s.title LIKE ? OR s.body LIKE ?)'; params.push('%'+q+'%', '%'+q+'%'); }
  if (lang) { where += ' AND s.language = ?'; params.push(lang); }

  const total = db.prepare(
    `SELECT COUNT(*) as c FROM snippets s ${where}`
  ).get(...params).c;

  const results = db.prepare(
    `SELECT s.id, s.title, s.language, s.view_count, u.username, s.created_at
     FROM snippets s JOIN users u ON s.owner_id = u.id
     ${where} ORDER BY s.created_at DESC LIMIT ? OFFSET ?`
  ).all(...params, per, (page - 1) * per);

  res.render('search', { results, q, lang, page, total, pages: Math.ceil(total / per) });
});

// ── Feature routers ───────────────────────────────────────────────────────────
app.use('/snippets', snippetsRouter);
app.use('/profile',  profileRouter);
app.use('/admin',    adminRouter);
app.use('/ai',       aiRouter);

// ── 404 / error ───────────────────────────────────────────────────────────────
app.use((req, res) => res.status(404).render('errors/404'));
app.use(errorMiddleware.handle);

// ── Boot ──────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 9000;
app.listen(PORT, () => console.log(`[CodeVault] listening on port ${PORT}`));

module.exports = app;
