'use strict';

const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');

const authRoutes  = require('./routes/auth');
const noteRoutes  = require('./routes/notes');
const adminRoutes = require('./routes/admin');
const db          = require('./services/db');

const app  = express();
const PORT = process.env.PORT || 9000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret:            process.env.SESSION_SECRET || 'dev-secret-change-me',
  resave:            false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge:   3600000
  }
}));

// Attach current user to every request for templates
app.use((req, _res, next) => {
  if (req.session && req.session.userId) {
    req.currentUser = db.getUserById(req.session.userId);
  }
  next();
});

app.get('/', (req, res) => {
  if (req.currentUser) {
    return res.redirect('/notes');
  }
  res.redirect('/auth/login');
});

app.use('/auth',  authRoutes);
app.use('/notes', noteRoutes);
app.use('/admin', adminRoutes);

// Generic 404
app.use((_req, res) => {
  res.status(404).send('<h1>404 — Page not found</h1>');
});

// Generic error handler
app.use((err, _req, res, _next) => {
  console.error('[ERROR]', err.stack || err.message);
  res.status(500).send('<h1>Internal Server Error</h1>');
});

db.initialize();
app.listen(PORT, '0.0.0.0', () => {
  console.log(`NoteFlow running on port ${PORT}`);
});

module.exports = app;