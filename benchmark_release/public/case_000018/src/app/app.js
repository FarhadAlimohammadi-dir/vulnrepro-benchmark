'use strict';

const express = require('express');
const session = require('express-session');
const path    = require('path');
const morgan  = require('morgan');

const logger      = require('./services/logger');
const { getDb }   = require('./db');
const authRouter  = require('./routes/auth');
const imageRouter = require('./routes/images');
const adminRouter = require('./routes/admin');
const apiRouter   = require('./routes/api');
const { requireAuth, requireAdmin } = require('./middleware/auth');

const app = express();

// ── View engine ─────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Body parsing ─────────────────────────────────────────────────────────────
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// ── Static assets ────────────────────────────────────────────────────────────
app.use('/static', express.static(path.join(__dirname, 'public')));

// ── Sessions ─────────────────────────────────────────────────────────────────
app.use(session({
  secret: process.env.SESSION_SECRET || 'vb-session-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 86400000 }
}));

// ── HTTP request logging ──────────────────────────────────────────────────────
app.use(morgan('combined', {
  stream: { write: msg => logger.http(msg.trim()) }
}));

// ── Inject current user into res.locals ──────────────────────────────────────
app.use((req, res, next) => {
  res.locals.currentUser  = null;
  res.locals.isAdmin      = false;
  if (req.session && req.session.userId) {
    const db   = getDb();
    const user = db.prepare('SELECT id, username, plan, is_admin FROM users WHERE id = ?')
                   .get(req.session.userId);
    if (user) {
      res.locals.currentUser = user;
      res.locals.isAdmin     = !!user.is_admin;
    }
  }
  next();
});

// ── Routes ────────────────────────────────────────────────────────────────────
app.use('/', authRouter);
app.use('/', imageRouter);
app.use('/admin', requireAuth, requireAdmin, adminRouter);
app.use('/api', apiRouter);

// ── Landing redirect ──────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'visionboard', version: '2.0.0' });
});

// ── 404 handler ───────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('error', {
    code: 404,
    message: 'The page you requested could not be found.'
  });
});

// ── Error handler ─────────────────────────────────────────────────────────────
app.use((err, req, res, _next) => {
  logger.error(`Unhandled error: ${err.message}\n${err.stack}`);
  res.status(500).render('error', {
    code: 500,
    message: 'An internal server error occurred.'
  });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  logger.info(`VisionBoard running on port ${PORT}`);
});

module.exports = app;