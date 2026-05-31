'use strict';

const express = require('express');
const path = require('path');
const session = require('express-session');
const morgan = require('morgan');

const { initDb } = require('./models/db');
const { agentState } = require('./services/agentState');

// Route modules
const authRoutes = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboard');
const workspaceRoutes = require('./routes/workspace');
const workflowRoutes = require('./routes/workflows');
const pluginRoutes = require('./routes/plugins');
const agentApiRoutes = require('./routes/agentApi');
const adminRoutes = require('./routes/admin');
const internalRoutes = require('./routes/internal');

const app = express();
const PORT = process.env.PORT || 9000;

// ── View engine ───────────────────────────────────────────────────────────────
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'nexusrelay-dev-secret-change-in-prod',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 86400000 }
}));

// Make agentState available to all views
app.use((req, res, next) => {
  res.locals.agentVersion = '2.4.0';
  res.locals.currentUser = req.session.username || null;
  res.locals.currentRole = req.session.role || null;
  next();
});

// ── Init DB ───────────────────────────────────────────────────────────────────
initDb();

// ── Routes ────────────────────────────────────────────────────────────────────
app.use('/', authRoutes);
app.use('/', dashboardRoutes);
app.use('/workspace', workspaceRoutes);
app.use('/workflows', workflowRoutes);
app.use('/api/plugins', pluginRoutes);
app.use('/api/agent', agentApiRoutes);
app.use('/admin', adminRoutes);
app.use('/_internal', internalRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '2.4.0', uptime: process.uptime() });
});

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', { title: 'Not Found', message: 'The page you requested does not exist.', code: 404 });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[error]', err.stack || err.message);
  res.status(500).render('error', { title: 'Server Error', message: 'An unexpected error occurred.', code: 500 });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[nexusrelay] Listening on port ${PORT}`);
});

module.exports = app;