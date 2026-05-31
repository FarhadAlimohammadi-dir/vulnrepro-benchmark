'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');
const SQLiteStore = require('connect-sqlite3')(session);

const authRoutes = require('./routes/auth');
const projectRoutes = require('./routes/projects');
const searchRoutes = require('./routes/search');
const profileRoutes = require('./routes/profile');
const feedbackRoutes = require('./routes/feedback');

const app = express();
const PORT = process.env.PORT || 9000;

// Middleware
app.use(morgan('combined'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret-key',
  resave: false,
  saveUninitialized: false,
  store: new SQLiteStore({ db: 'sessions.db', dir: './db' }),
  cookie: {
    maxAge: 1000 * 60 * 60 * 24,
    httpOnly: true
  }
}));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Make session user available in all views
app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  next();
});

// Routes
app.use('/auth', authRoutes);
app.use('/projects', projectRoutes);
app.use('/search', searchRoutes);
app.use('/profile', profileRoutes);
app.use('/feedback', feedbackRoutes);

app.get('/', (req, res) => {
  const db = require('./db/database');
  const projects = db.prepare(
    'SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id = u.id ORDER BY p.created_at DESC LIMIT 6'
  ).all();
  res.render('index', { projects, title: 'ProjectHub - Home' });
});

app.get('/dashboard', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/auth/login');
  }
  const db = require('./db/database');
  const myProjects = db.prepare(
    'SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC'
  ).all(req.session.user.id);
  const recentFeedback = db.prepare(
    'SELECT f.*, u.username FROM feedback f JOIN users u ON f.user_id = u.id ORDER BY f.created_at DESC LIMIT 5'
  ).all();
  res.render('dashboard', {
    title: 'Dashboard',
    projects: myProjects,
    feedback: recentFeedback
  });
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use((req, res) => {
  res.status(404).render('error', { title: '404 Not Found', message: 'Page not found' });
});

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).render('error', { title: 'Server Error', message: 'Something went wrong' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`ProjectHub running on port ${PORT}`);
});

module.exports = app;