'use strict';
/**
 * NovaSpark IDE — HTTP server entry point
 */
const path    = require('path');
const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const SQLiteStore = require('connect-sqlite3')(session);

const { PORT, SESSION_SECRET, DB_PATH, APP_VERSION } = require('./config');
const { logger } = require('./logger');
const { initSchema, seedData } = require('./db');

// ── Routes ────────────────────────────────────────────────────────────────────
const authRoutes      = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboard');
const projectsRoutes  = require('./routes/projects');
const profileRoutes   = require('./routes/profile');
const adminRoutes     = require('./routes/admin');
const lspRoutes       = require('./routes/lsp');

// ── Database setup ────────────────────────────────────────────────────────────
initSchema();
seedData();

// ── Express app ───────────────────────────────────────────────────────────────
const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(morgan('combined', {
  stream: { write: msg => logger.info(msg.trim(), { component: 'http' }) },
}));

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.use(session({
  store:             new SQLiteStore({ db: 'sessions.db', dir: '.' }),
  secret:            SESSION_SECRET,
  resave:            false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge:   8 * 60 * 60 * 1000, // 8 hours
  },
}));

// Attach app metadata to every response for template use
app.use((req, res, next) => {
  res.locals.appVersion = APP_VERSION;
  res.locals.appName    = 'NovaSpark IDE';
  next();
});

// ── Route mounting ────────────────────────────────────────────────────────────
app.use('/',         authRoutes);
app.use('/',         dashboardRoutes);
app.use('/projects', projectsRoutes);
app.use('/profile',  profileRoutes);
app.use('/admin',    adminRoutes);
app.use('/lsp',      lspRoutes);

// ── 404 ───────────────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('error', { message: 'Page not found', code: 404 });
});

// ── Global error handler ──────────────────────────────────────────────────────
app.use((err, req, res, next) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).render('error', { message: 'Internal server error', code: 500 });
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, '0.0.0.0', () => {
  logger.info(`NovaSpark IDE server started`, { port: PORT, version: APP_VERSION, env: process.env.NODE_ENV || 'development' });
});

module.exports = app;