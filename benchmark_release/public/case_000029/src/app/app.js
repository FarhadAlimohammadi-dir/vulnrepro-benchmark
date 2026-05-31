'use strict';

const express       = require('express');
const session       = require('express-session');
const morgan        = require('morgan');
const path          = require('path');

const db            = require('./db');
const authRouter    = require('./routes/auth');
const docsRouter    = require('./routes/docs');
const adminRouter   = require('./routes/admin');
const apiRouter     = require('./routes/api');
const { requireAuth, requireAdmin } = require('./middleware/auth');

const app = express();

// ── View engine ───────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Static assets ─────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ── Body parsing ──────────────────────────────────────────────────────────────
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// ── Sessions ──────────────────────────────────────────────────────────────────
app.use(session({
  secret: 'dv-s3cr3t-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 8 * 60 * 60 * 1000 }
}));

// ── HTTP logging ──────────────────────────────────────────────────────────────
app.use(morgan('dev'));

// ── Locals available in all views ─────────────────────────────────────────────
app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  next();
});

// ── Routes ────────────────────────────────────────────────────────────────────
app.use('/',       authRouter);
app.use('/docs',   requireAuth, docsRouter);
app.use('/admin',  requireAuth, requireAdmin, adminRouter);
app.use('/api',    apiRouter);

// ── 404 handler ───────────────────────────────────────────────────────────────
app.use((_req, res) => {
  res.status(404).render('error', { title: 'Not Found', message: 'The page you requested does not exist.', code: 404 });
});

// ── Global error handler ──────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error('[error]', err.stack || err.message);
  res.status(500).render('error', { title: 'Server Error', message: 'An unexpected error occurred.', code: 500 });
});

app.listen(9000, () => console.log('[docvault] listening on :9000'));