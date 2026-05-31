'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');

const { initDb } = require('./db');
const authRoutes = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboards');
const apiRoutes = require('./routes/api');

const app = express();
const PORT = process.env.PORT || 9000;

// Initialize database
initDb();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '..', 'views'));

// Middleware
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, '..', 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret-change-in-prod',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000
  }
}));

// Attach user to request if session exists
app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  next();
});

// Routes
app.use('/auth', authRoutes);
app.use('/dashboards', dashboardRoutes);
app.use('/api', apiRoutes);

// Home
app.get('/', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/auth/login');
  }
  const db = require('./db').getDb();
  const dashboards = db.prepare(`
    SELECT d.id, d.title, d.created_at, u.username as owner
    FROM dashboards d
    JOIN users u ON d.user_id = u.id
    WHERE d.user_id = ? OR d.is_public = 1
    ORDER BY d.created_at DESC
    LIMIT 20
  `).all(req.session.user.id);

  res.render('index', { dashboards, user: req.session.user });
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '1.0.0' });
});

// 404
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.message);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`DataViz Studio running on port ${PORT}`);
});

module.exports = app;