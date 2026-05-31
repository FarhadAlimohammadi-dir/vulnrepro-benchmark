'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');
const crypto = require('crypto');

const authRouter = require('./routes/auth');
const cardsRouter = require('./routes/cards');
const adminRouter = require('./routes/admin');
const searchRouter = require('./routes/search');

const app = express();
const PORT = process.env.PORT || 9000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(morgan('combined'));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    sameSite: 'lax',
    maxAge: 24 * 60 * 60 * 1000
  }
}));

function sameOrigin(req) {
  const origin = req.get('origin');
  if (!origin) return true;
  return origin === `${req.protocol}://${req.get('host')}`;
}

function ensureCsrfToken(req) {
  if (!req.session.csrfToken) {
    req.session.csrfToken = crypto.randomBytes(32).toString('base64url');
  }
  return req.session.csrfToken;
}

function validateBrowserStateChange(req, res, next) {
  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  if (!mutating) return next();

  if (!sameOrigin(req)) {
    return res.status(403).json({ error: 'Invalid request origin.' });
  }

  if (req.is('application/x-www-form-urlencoded') || req.is('multipart/form-data')) {
    const submitted = req.body && (req.body._csrf || req.get('x-csrf-token'));
    if (!submitted || submitted !== req.session.csrfToken) {
      return res.status(403).json({ error: 'Invalid CSRF token.' });
    }
  }

  next();
}

app.use(validateBrowserStateChange);

// Attach user and per-session CSRF token to templates
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  res.locals.csrfToken = ensureCsrfToken(req);
  next();
});

app.use((req, res, next) => {
  const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  if (mutating && req.path.startsWith('/api/') && !req.is('application/json')) {
    return res.status(415).json({ error: 'JSON request body required.' });
  }
  next();
});

app.get('/', (req, res) => {
  if (req.session.user) {
    return res.redirect('/dashboard');
  }
  res.render('login', { error: null });
});

app.get('/dashboard', requireLogin, (req, res) => {
  const db = require('./db/database').getDb();
  const cards = db.prepare(`
    SELECT c.id, c.title, c.created_at, u.username as author
    FROM cards c
    JOIN users u ON c.user_id = u.id
    LEFT JOIN shares s ON s.card_id = c.id AND s.shared_with = ?
    WHERE c.is_public = 1 OR c.user_id = ? OR ? = 'admin' OR s.id IS NOT NULL
    ORDER BY c.created_at DESC
    LIMIT 20
  `).all(req.session.user.id, req.session.user.id, req.session.user.role);
  res.render('dashboard', { cards });
});

app.use('/auth', authRouter);
app.use('/api/cards', cardsRouter);
app.use('/api/admin', adminRouter);
app.use('/search', searchRouter);

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

function requireLogin(req, res, next) {
  if (!req.session.user) {
    return res.redirect('/');
  }
  next();
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`CollabDocs running on port ${PORT}`);
});

module.exports = app;
