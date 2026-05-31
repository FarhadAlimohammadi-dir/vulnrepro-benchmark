'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');
const crypto = require('crypto');

const authRouter = require('./routes/auth');
const dashboardRouter = require('./routes/dashboard');
const pluginsRouter = require('./routes/plugins');
const feedbackRouter = require('./routes/feedback');
const adminRouter = require('./routes/admin');
const apiRouter = require('./routes/api');

const app = express();

// ── Middleware ──────────────────────────────────────────────────────────────
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, httpOnly: true, sameSite: 'lax', maxAge: 86400000 }
}));

// ── View engine ─────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Locals available to every template ──────────────────────────────────────
app.use((req, res, next) => {
  if (req.session.user && !req.session.csrfToken) {
    req.session.csrfToken = crypto.randomBytes(32).toString('hex');
  }
  res.locals.currentUser = req.session.user || null;
  res.locals.flashMessage = req.session.flash || null;
  res.locals.csrfToken = req.session.csrfToken || '';
  delete req.session.flash;
  next();
});

// ── Routes ───────────────────────────────────────────────────────────────────
app.use('/', authRouter);
app.use('/', dashboardRouter);
app.use('/plugins', pluginsRouter);
app.use('/feedback', feedbackRouter);
app.use('/admin', adminRouter);
app.use('/api', apiRouter);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: Date.now(), version: '2.1.0' });
});

// 404
app.use((req, res) => {
  res.status(404).render('error', { code: 404, message: 'Page not found' });
});

// General error handler
app.use((err, req, res, _next) => {
  console.error('[error]', err.stack);
  res.status(500).render('error', { code: 500, message: 'Internal server error' });
});

module.exports = app;
