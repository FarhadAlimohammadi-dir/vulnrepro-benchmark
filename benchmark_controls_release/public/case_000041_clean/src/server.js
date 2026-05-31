'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');

const db = require('./src/db');
const { seedDatabase } = require('./src/seed');
const authMiddleware = require('./src/middleware/auth');
const auditLogger = require('./src/middleware/audit');

const authRoutes = require('./src/routes/auth');
const dashboardRoutes = require('./src/routes/dashboard');
const policyRoutes = require('./src/routes/policies');
const apiRoutes = require('./src/routes/api');
const adminRoutes = require('./src/routes/admin');
const profileRoutes = require('./src/routes/profile');

const app = express();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'src/views'));

// Static assets
app.use(express.static(path.join(__dirname, 'public')));

// Body parsing
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// HTTP logging
app.use(morgan('combined'));

// Session
app.use(session({
  secret: process.env.SESSION_SECRET || 'iam-studio-dev-secret',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, maxAge: 8 * 60 * 60 * 1000 }
}));

// Audit logging middleware (attaches to res.locals)
app.use(auditLogger.attach);

// Routes
app.use('/', authRoutes);
app.use('/', dashboardRoutes);
app.use('/policies', policyRoutes);
app.use('/api', apiRoutes);
app.use('/admin', adminRoutes);
app.use('/profile', profileRoutes);

// Root redirect
app.get('/', (req, res) => {
  if (req.session.userId) return res.redirect('/dashboard');
  res.redirect('/login');
});

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', {
    title: 'Page Not Found',
    message: 'The resource you requested could not be found.',
    code: 404,
    user: req.session.username || null
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack);
  res.status(500).render('error', {
    title: 'Internal Server Error',
    message: 'An unexpected error occurred. Please try again.',
    code: 500,
    user: req.session.username || null
  });
});

// Seed and start
seedDatabase();

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  console.log(`[INFO] IAM Policy Studio running on port ${PORT}`);
});

module.exports = app;