'use strict';

const express = require('express');
const session = require('express-session');
const SQLiteStore = require('connect-sqlite3')(session);
const morgan = require('morgan');
const path = require('path');

const authRoutes = require('./routes/auth');
const apiRoutes = require('./routes/api');
const docsRoutes = require('./routes/docs');
const adminRoutes = require('./routes/admin');
const userRoutes = require('./routes/user');

const app = express();
const PORT = process.env.PORT || 9000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '../views'));

app.use(morgan('combined'));
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(express.static(path.join(__dirname, '../public')));

app.use(session({
  store: new SQLiteStore({ db: 'sessions.db', dir: '/tmp' }),
  secret: process.env.SESSION_SECRET || 'dev-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: {
    maxAge: 1000 * 60 * 60 * 8, // 8 hours
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production'
  }
}));

// Attach user to res.locals for templates
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  next();
});

app.use((req, res, next) => {
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(req.method);
  if (!unsafe || !req.session.user) return next();
  const origin = req.get('origin');
  const referer = req.get('referer');
  const candidate = origin || referer;
  if (candidate) {
    try {
      if (new URL(candidate).host !== req.get('host')) {
        return res.status(403).json({ error: 'cross-site request rejected' });
      }
    } catch (_) {
      return res.status(403).json({ error: 'invalid request origin' });
    }
  }
  if (req.get('sec-fetch-site') === 'cross-site') {
    return res.status(403).json({ error: 'cross-site request rejected' });
  }
  next();
});

app.use('/auth', authRoutes);
app.use('/api', apiRoutes);
app.use('/docs', docsRoutes);
app.use('/admin', adminRoutes);
app.use('/user', userRoutes);

app.get('/', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/auth/login');
  }
  res.redirect('/docs');
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[INFO] API Docs Portal running on port ${PORT}`);
});

module.exports = app;
