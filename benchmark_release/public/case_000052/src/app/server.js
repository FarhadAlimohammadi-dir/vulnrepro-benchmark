'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');

const { initDb } = require('./models/db');
const { seedDatabase } = require('./scripts/seed');
const authRoutes = require('./routes/auth');
const oauthRoutes = require('./routes/oauth');
const apiRoutes = require('./routes/api');
const adminRoutes = require('./routes/admin');
const logger = require('./services/logger');

const app = express();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static files
app.use(express.static(path.join(__dirname, '..', 'public')));

// Body parsing
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(express.json({ limit: '50mb' }));

// HTTP request logging
app.use(morgan('combined', {
  stream: { write: msg => logger.http(msg.trim()) }
}));

// Session
app.use(session({
  secret: process.env.SESSION_SECRET || 'codeflow-session-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: false,
    secure: false,
    maxAge: 24 * 60 * 60 * 1000
  },
  name: 'codeflow.sid'
}));

// Initialize DB and seed
const db = initDb();
seedDatabase(db);

// Make db available to routes
app.use((req, res, next) => {
  req.db = db;
  next();
});

// Routes
app.use('/', authRoutes);
app.use('/', oauthRoutes);
app.use('/api', apiRoutes);
app.use('/admin', adminRoutes);

// Home
app.get('/', (req, res) => {
  const user = req.session.user || null;
  const recentApps = db.prepare(
    'SELECT * FROM oauth_clients ORDER BY created_at DESC LIMIT 5'
  ).all();
  res.render('home', { user, recentApps, page: 'home' });
});

// Health check
app.get('/health', (req, res) => {
  const stats = {
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    users: db.prepare('SELECT COUNT(*) as cnt FROM users').get().cnt,
    clients: db.prepare('SELECT COUNT(*) as cnt FROM oauth_clients').get().cnt,
    tokens: db.prepare('SELECT COUNT(*) as cnt FROM access_tokens').get().cnt
  };
  res.json(stats);
});

// 404
app.use((req, res) => {
  res.status(404).render('error', {
    user: req.session.user || null,
    title: 'Page Not Found',
    message: 'The page you requested could not be found.',
    code: 404
  });
});

// Error handler
app.use((err, req, res, next) => {
  logger.error(`Unhandled error: ${err.message}`, { stack: err.stack });
  res.status(500).render('error', {
    user: req.session.user || null,
    title: 'Internal Server Error',
    message: 'An unexpected error occurred. Please try again later.',
    code: 500
  });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  logger.info(`CodeFlow OAuth Server started on port ${PORT}`);
});

module.exports = app;