'use strict';

const express       = require('express');
const session       = require('express-session');
const path          = require('path');
const logger        = require('./services/logger');
const requestLogger = require('./middleware/requestLogger');

// Ensure DB schema exists before anything else
require('./db');

const app = express();

// ── View engine ───────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(requestLogger);
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  name:              'cb_session',
  secret:            process.env.SESSION_SECRET || 'cb-session-secret-2026',
  resave:            false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge:   3600000,
    sameSite: 'lax'
  }
}));

// ── Routes ────────────────────────────────────────────────────────────────────
const authRoutes       = require('./routes/auth');
const uiRoutes         = require('./routes/ui');
const pipelineRoutes   = require('./routes/pipelines');
const connectorRoutes  = require('./routes/connectors');
const adminRoutes      = require('./routes/admin');

app.use('/',              authRoutes);
app.use('/',              uiRoutes);
app.use('/api/pipelines', pipelineRoutes);
app.use('/api/connectors',connectorRoutes);
app.use('/api/admin',     adminRoutes);

// ── Health ────────────────────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ status: 'ok', ts: Date.now() }));

// ── Global error handler ──────────────────────────────────────────────────────
app.use((err, req, res, next) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  if (req.path.startsWith('/api/')) {
    return res.status(500).json({ error: 'Internal server error' });
  }
  res.status(500).render('error', { message: 'Internal server error', code: 500 });
});

// ── 404 ───────────────────────────────────────────────────────────────────────
app.use((req, res) => {
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'Not found' });
  }
  res.status(404).render('error', { message: 'Page not found', code: 404 });
});

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = parseInt(process.env.PORT || '9000', 10);
app.listen(PORT, '0.0.0.0', () => {
  logger.info(`ContextBridge listening on :${PORT}`);
});

module.exports = app;