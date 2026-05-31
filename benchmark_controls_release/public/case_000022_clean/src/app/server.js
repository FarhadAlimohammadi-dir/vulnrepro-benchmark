'use strict';

const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');
const crypto  = require('crypto');

const { initDb }          = require('./db');
const { requireAuth, requireAdmin } = require('./middleware/auth');
const logger              = require('./services/logger');

const authRouter    = require('./routes/auth');
const issuesRouter  = require('./routes/issues');
const tasksRouter   = require('./routes/tasks');
const reposRouter   = require('./routes/repos');
const adminRouter   = require('./routes/admin');
const pagesRouter   = require('./routes/pages');

const app = express();

// ── View engine ───────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(morgan('combined', { stream: { write: m => logger.info(m.trim()) } }));
app.use(express.json({ limit: '256kb' }));
app.use(express.urlencoded({ extended: true, limit: '64kb' }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: process.env.SESSION_SECRET || 'cp-dev-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 7200000 }
}));

// Expose session user to all templates
app.use((req, res, next) => {
  res.locals.user     = req.session.username || null;
  res.locals.role     = req.session.role     || null;
  res.locals.userId   = req.session.userId   || null;
  next();
});

// ── Routes ────────────────────────────────────────────────────────────────────
app.use('/',            authRouter);
app.use('/',            pagesRouter);
app.use('/api/issues',  issuesRouter);
app.use('/api/tasks',   tasksRouter);
app.use('/api/repos',   reposRouter);
app.use('/admin',       adminRouter);

// Health probe (used by Docker healthcheck)
app.get('/health', (_req, res) => res.json({ status: 'ok', ts: Date.now() }));

// 404
app.use((_req, res) => res.status(404).render('error', { code: 404, message: 'Page not found' }));

// 500
app.use((err, _req, res, _next) => {
  logger.error(err.stack || err.message);
  res.status(500).render('error', { code: 500, message: 'Internal server error' });
});

// ── Boot ──────────────────────────────────────────────────────────────────────
const PORT = parseInt(process.env.PORT || '9000', 10);
initDb();
app.listen(PORT, '0.0.0.0', () => logger.info(`CodePilot listening on :${PORT}`));

module.exports = app;