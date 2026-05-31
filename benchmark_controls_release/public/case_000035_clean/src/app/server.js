'use strict';

const express = require('express');
const session = require('express-session');
const path = require('path');
const morgan = require('morgan');

const { initDB } = require('./models/database');
const { seedDatabase } = require('./seed');
const authRoutes = require('./routes/auth');
const accountRoutes = require('./routes/accounts');
const requestRoutes = require('./routes/requests');
const adminRoutes = require('./routes/admin');
const profileRoutes = require('./routes/profile');
const auditRoutes = require('./routes/audit');
const uiRoutes = require('./routes/ui');

const app = express();
const PORT = process.env.PORT || 9000;

// View engine setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static assets
app.use(express.static(path.join(__dirname, 'public')));

// Request parsing
app.use(express.json({ limit: '5mb' }));
app.use(express.urlencoded({ extended: true, limit: '5mb' }));

// HTTP request logging
app.use(morgan('combined'));

// Session configuration
app.use(session({
  secret: process.env.SESSION_SECRET || 'gw-dev-secret-change-in-prod',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge: 8 * 60 * 60 * 1000, // 8 hours
    sameSite: 'lax'
  },
  name: 'gw.sid'
}));

// Attach user context to res.locals for templates
app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  res.locals.flash = req.session.flash || null;
  if (req.session.flash) delete req.session.flash;
  next();
});

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/accounts', accountRoutes);
app.use('/api/requests', requestRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/profile', profileRoutes);
app.use('/api/audit', auditRoutes);

// UI Routes
app.use('/', uiRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), ts: new Date().toISOString() });
});

// 404 handler
app.use((req, res) => {
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'Endpoint not found' });
  }
  res.status(404).render('error', { title: 'Not Found', message: 'Page not found', code: 404 });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack || err.message);
  if (req.path.startsWith('/api/')) {
    return res.status(500).json({ error: 'Internal server error' });
  }
  res.status(500).render('error', { title: 'Server Error', message: 'An unexpected error occurred.', code: 500 });
});

// Bootstrap
(async () => {
  try {
    initDB();
    seedDatabase();
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`[INFO] Gateway Portal running on port ${PORT}`);
    });
  } catch (err) {
    console.error('[FATAL] Startup failed:', err);
    process.exit(1);
  }
})();

module.exports = app;