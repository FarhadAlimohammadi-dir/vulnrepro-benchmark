'use strict';

const express = require('express');
const session = require('express-session');
const compression = require('compression');
const morgan = require('morgan');
const path = require('path');

const logger = require('./services/logger');
const authRoutes = require('./routes/auth');
const articleRoutes = require('./routes/articles');
const userRoutes = require('./routes/users');
const adminRoutes = require('./routes/admin');
const pageRoutes = require('./routes/pages');

const app = express();

// Middleware
app.use(compression());
app.use(morgan('combined', {
  stream: { write: msg => logger.http(msg.trim()) }
}));
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// Sessions
app.use(session({
  secret: process.env.SESSION_SECRET || 'cf-platform-dev-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 4 * 60 * 60 * 1000 // 4 hours
  }
}));

// View engine — EJS with layout support
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Simple layout middleware: wraps view body in layout template
app.use((req, res, next) => {
  const originalRender = res.render.bind(res);
  res.render = function (view, locals, callback) {
    const opts = locals || {};
    originalRender(view, opts, (err, html) => {
      if (err) return next(err);
      if (opts.layout === false) {
        if (callback) return callback(null, html);
        return res.send(html);
      }
      const layoutLocals = Object.assign({}, opts, { body: html });
      originalRender('layout', layoutLocals, (err2, full) => {
        if (err2) return next(err2);
        if (callback) return callback(null, full);
        res.send(full);
      });
    });
  };
  next();
});

// Routes
app.use('/', authRoutes);
app.use('/', pageRoutes);
app.use('/api/articles', articleRoutes);
app.use('/api/users', userRoutes);
app.use('/api/admin', adminRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'contentflow', version: '2.1.0' });
});

// 404 handler
app.use((req, res) => {
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'Not found' });
  }
  res.status(404).render('error', { message: 'Page not found', status: 404 });
});

// Global error handler
app.use((err, req, res, next) => {
  logger.error('Unhandled error', { err: err.message, stack: err.stack, path: req.path });
  if (req.path.startsWith('/api/')) {
    return res.status(500).json({ error: 'Internal server error' });
  }
  res.status(500).render('error', { message: 'Internal server error', status: 500 });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  logger.info(`ContentFlow platform running on port ${PORT}`);
});

module.exports = app;