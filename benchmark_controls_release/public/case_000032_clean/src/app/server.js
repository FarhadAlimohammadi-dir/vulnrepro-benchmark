'use strict';

const express = require('express');
const cookieParser = require('cookie-parser');
const morgan = require('morgan');
const path = require('path');

const { initDb } = require('./models/database');
const { seedDatabase } = require('./models/seed');
const authMiddleware = require('./middleware/auth');
const rateLimiter = require('./middleware/ratelimit');

const indexRouter = require('./routes/index');
const authRouter = require('./routes/auth');
const oauthRouter = require('./routes/oauth');
const pixelRouter = require('./routes/pixel');
const graphRouter = require('./routes/graph');
const adminRouter = require('./routes/admin');
const apiRouter = require('./routes/api');

const app = express();
const PORT = process.env.PORT || 9000;

// Initialize database and seed
const db = initDb();
seedDatabase(db);

app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Make db available to routes
app.use((req, res, next) => {
  req.db = db;
  next();
});

function sameOriginBrowserWrite(req) {
  const host = req.get('host');
  const expected = `${req.protocol}://${host}`;
  const origin = req.get('origin');
  if (origin) {
    return origin === expected;
  }
  const referer = req.get('referer');
  if (referer) {
    try {
      return new URL(referer).origin === expected;
    } catch (_) {
      return false;
    }
  }
  return true;
}

app.use((req, res, next) => {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
    return next();
  }
  if (!req.cookies || !req.cookies.sid) {
    return next();
  }
  const fetchSite = req.get('sec-fetch-site');
  if (fetchSite && fetchSite !== 'same-origin' && fetchSite !== 'same-site' && fetchSite !== 'none') {
    return res.status(403).json({ error: 'Cross-site write rejected' });
  }
  if (!sameOriginBrowserWrite(req)) {
    return res.status(403).json({ error: 'Cross-site write rejected' });
  }
  return next();
});

// Routes
app.use('/', indexRouter);
app.use('/', authRouter);
app.use('/oauth', oauthRouter);
app.use('/pixel', pixelRouter);
app.use('/graph', graphRouter);
app.use('/admin', adminRouter);
app.use('/api', apiRouter);

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', {
    title: 'Page Not Found',
    message: 'The page you are looking for does not exist.',
    statusCode: 404,
    user: null
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack || err.message);
  res.status(500).render('error', {
    title: 'Internal Server Error',
    message: 'An unexpected error occurred. Please try again later.',
    statusCode: 500,
    user: null
  });
});

app.listen(PORT, () => {
  console.log(`[INFO] Analytics Platform running on http://localhost:${PORT}`);
  console.log(`[INFO] Environment: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;
