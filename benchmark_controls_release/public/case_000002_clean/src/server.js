'use strict';

const express = require('express');
const session = require('express-session');
const path = require('path');
const fs = require('fs');

const config = require('./config');
const logger = require('./lib/logger');
const db = require('./lib/db');
const auditMiddleware = require('./middleware/audit');
const flashMiddleware = require('./middleware/flash');

// Ensure data dirs exist before DB init
[config.dataDir, config.workspaceRoot, config.uploadDir].forEach(d => {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
});

db.init();
db.seedDemoData();

const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(session({
  secret: config.sessionSecret,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 7 * 24 * 60 * 60 * 1000
  },
}));

app.use(flashMiddleware);

// Make session user available to all templates
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  next();
});

app.use((req, res, next) => {
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(req.method);
  if (!unsafe || !req.session.user) return next();

  const origin = req.get('origin');
  const referer = req.get('referer');
  const host = req.get('host');
  const candidate = origin || referer;

  if (candidate) {
    try {
      if (new URL(candidate).host !== host) {
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

app.use(auditMiddleware);

// Routes
app.use('/',           require('./routes/home'));
app.use('/auth',       require('./routes/auth'));
app.use('/workspaces', require('./routes/workspaces'));
app.use('/projects',   require('./routes/projects'));
app.use('/snippets',   require('./routes/snippets'));
app.use('/api-keys',   require('./routes/api_keys'));
app.use('/activity',   require('./routes/activity'));
app.use('/profile',    require('./routes/profile'));
app.use('/admin',      require('./routes/admin'));

// 404
app.use((req, res) => {
  res.status(404).render('error', { message: 'Page not found' });
});

// Error handler
app.use((err, req, res, next) => {
  logger.error('unhandled error', { err: err.message, stack: err.stack });
  res.status(500).render('error', { message: 'Internal server error' });
});

const PORT = config.port;
app.listen(PORT, '0.0.0.0', () => {
  logger.info('claspace listening', { port: PORT, mode: process.env.NODE_ENV });
});

module.exports = app;
