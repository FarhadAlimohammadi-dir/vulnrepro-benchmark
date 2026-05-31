'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');

const { initDb } = require('./db');
const logger = require('./services/logger');
const authMiddleware = require('./middleware/auth');
const adminMiddleware = require('./middleware/admin');

const authRoutes = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboard');
const runsRoutes = require('./routes/runs');
const apiRoutes = require('./routes/api');
const analyticsRoutes = require('./routes/analytics');
const adminRoutes = require('./routes/admin');
const profileRoutes = require('./routes/profile');

const app = express();
const PORT = process.env.PORT || 9000;

// Initialize database and seed data
initDb();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static assets
app.use(express.static(path.join(__dirname, 'public')));

// Request parsing
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// HTTP request logging
app.use(morgan('combined', {
  stream: { write: (msg) => logger.info(msg.trim()) }
}));

// Session management
app.use(session({
  secret: process.env.SESSION_SECRET || 'neuralops-session-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 3600000 }
}));

// Attach user info to locals for templates
app.use((req, res, next) => {
  res.locals.currentUser = req.session.username || null;
  res.locals.currentRole = req.session.role || null;
  res.locals.flash = req.session.flash || null;
  if (req.session.flash) delete req.session.flash;
  next();
});

// Health check (public)
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'neuralops-platform', ts: Date.now() });
});

// Route mounts
app.use('/', authRoutes);
app.use('/dashboard', authMiddleware, dashboardRoutes);
app.use('/runs', authMiddleware, runsRoutes);
app.use('/profile', authMiddleware, profileRoutes);
app.use('/admin', authMiddleware, adminMiddleware, adminRoutes);
app.use('/api', authMiddleware, apiRoutes);
app.use('/analytics', authMiddleware, analyticsRoutes);

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', { code: 404, message: 'Page not found' });
});

// Generic error handler
app.use((err, req, res, next) => {
  logger.error(`Unhandled error: ${err.message}`);
  res.status(500).render('error', { code: 500, message: 'Internal server error' });
});

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`NeuralOps Platform running on port ${PORT}`);
});

module.exports = app;
