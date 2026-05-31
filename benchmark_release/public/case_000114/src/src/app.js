'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const helmet = require('helmet');
const path = require('path');
const { initSchema } = require('./db');

const authRoutes = require('./routes/auth');
const documentRoutes = require('./routes/documents');
const adminRoutes = require('./routes/admin');
const profileRoutes = require('./routes/profile');

initSchema();

const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '..', 'views'));

// Middleware
app.use(morgan('combined'));
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(express.static(path.join(__dirname, '..', 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret-change-me',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: false,
    maxAge: 86400000,
  },
}));

// Attach user to res.locals for templates
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  next();
});

// Routes
app.use('/auth', authRoutes);
app.use('/documents', documentRoutes);
app.use('/admin', adminRoutes);
app.use('/profile', profileRoutes);

app.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/documents');
  res.redirect('/auth/login');
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', ts: Date.now() });
});

// 404
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.message, err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`DocCollab listening on port ${PORT}`);
});

module.exports = app;