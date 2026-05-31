'use strict';

const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');

const { db, seedDb }         = require('./db');
const authRouter             = require('./routes/auth');
const dashboardRouter        = require('./routes/dashboard');
const apiRouter              = require('./routes/api');
const adminRouter            = require('./routes/admin');
const { requireAuth }        = require('./middleware/auth');

const app = express();

// ── View engine ──────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Static assets ────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ── Body / session middleware ────────────────────────────────────
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(morgan('tiny'));
app.use(session({
  secret: 'nx-session-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 86400000 }
}));

// ── Seed database ────────────────────────────────────────────────
seedDb();

// ── Routes ───────────────────────────────────────────────────────
app.use('/', authRouter);
app.use('/', dashboardRouter);
app.use('/api', apiRouter);
app.use('/admin', adminRouter);

// ── Health ───────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ status: 'ok', ts: Date.now() }));

// ── 404 handler ──────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('error', { title: '404 Not Found', message: 'The page you requested does not exist.', user: req.session.username || null });
});

// ── Error handler ────────────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('[nexusai error]', err.stack || err.message);
  res.status(500).render('error', { title: 'Internal Server Error', message: 'Something went wrong. Our team has been notified.', user: req.session.username || null });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => console.log(`[nexusai] Listening on :${PORT}`));

module.exports = app;