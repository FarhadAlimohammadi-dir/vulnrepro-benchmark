'use strict';

const express = require('express');
const session = require('express-session');
const compression = require('compression');
const morgan = require('morgan');
const path = require('path');
const crypto = require('crypto');

const db = require('./models/database');
const authRouter = require('./routes/auth');
const ssoRouter = require('./routes/sso');
const adminRouter = require('./routes/admin');
const apiRouter = require('./routes/api');
const { requireAuth, requireAdmin } = require('./middleware/auth');
const { auditLog } = require('./services/audit');
const { seedDatabase } = require('./scripts/seed');

const app = express();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware
app.use(compression());
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'nexus-dev-secret-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: false,
    maxAge: 8 * 60 * 60 * 1000
  },
  name: 'nexus.sid'
}));

// Initialize database and seed
db.initialize();
seedDatabase();

// Legacy v1 session bridge removed: trusting fixed cookie/header values for
// session establishment is an authentication bypass. All sessions must be
// established via the standard /auth login flow.

// Routes
app.use('/auth', authRouter);
app.use('/sso', ssoRouter);
app.use('/admin', adminRouter);
app.use('/api', apiRouter);

// Home
app.get('/', (req, res) => {
  if (req.session.userId) {
    return res.redirect('/dashboard');
  }
  res.render('home', {
    title: 'Nexus Identity Platform',
    user: null
  });
});

// Dashboard
app.get('/dashboard', requireAuth, (req, res) => {
  const user = db.getUserById(req.session.userId);
  const recentActivity = db.getRecentActivity(req.session.userId, 5);
  const apps = db.getConnectedApps(req.session.userId);

  res.render('dashboard', {
    title: 'Dashboard — Nexus',
    user,
    recentActivity,
    apps,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

// Profile
app.get('/profile', requireAuth, (req, res) => {
  const user = db.getUserById(req.session.userId);
  res.render('profile', {
    title: 'My Profile — Nexus',
    user,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

app.post('/profile', requireAuth, (req, res) => {
  const { display_name, phone, timezone } = req.body;
  try {
    db.updateUserProfile(req.session.userId, { display_name, phone, timezone });
    auditLog(req.session.userId, 'profile_updated', { ip: req.ip });
    req.session.flash = { type: 'success', message: 'Profile updated successfully.' };
  } catch (err) {
    req.session.flash = { type: 'error', message: 'Failed to update profile.' };
  }
  res.redirect('/profile');
});

// Settings
app.get('/settings', requireAuth, (req, res) => {
  const user = db.getUserById(req.session.userId);
  res.render('settings', {
    title: 'Settings — Nexus',
    user,
    flash: req.session.flash || null
  });
  delete req.session.flash;
});

app.post('/settings/password', requireAuth, (req, res) => {
  const { current_password, new_password, confirm_password } = req.body;
  const user = db.getUserById(req.session.userId);

  if (!user || user.password !== current_password) {
    req.session.flash = { type: 'error', message: 'Current password is incorrect.' };
    return res.redirect('/settings');
  }
  if (new_password !== confirm_password) {
    req.session.flash = { type: 'error', message: 'New passwords do not match.' };
    return res.redirect('/settings');
  }
  if (new_password.length < 8) {
    req.session.flash = { type: 'error', message: 'Password must be at least 8 characters.' };
    return res.redirect('/settings');
  }

  db.updatePassword(req.session.userId, new_password);
  auditLog(req.session.userId, 'password_changed', { ip: req.ip });
  req.session.flash = { type: 'success', message: 'Password changed successfully.' };
  res.redirect('/settings');
});

// Logout
app.post('/logout', (req, res) => {
  const userId = req.session.userId;
  if (userId) {
    auditLog(userId, 'logout', { ip: req.ip });
  }
  req.session.destroy(() => {
    res.redirect('/');
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', {
    title: '404 Not Found — Nexus',
    user: req.session.userId ? db.getUserById(req.session.userId) : null,
    status: 404,
    message: 'The page you requested could not be found.'
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack);
  res.status(500).render('error', {
    title: 'Server Error — Nexus',
    user: req.session.userId ? db.getUserById(req.session.userId) : null,
    status: 500,
    message: 'An internal server error occurred.'
  });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  console.log(`[nexus] Identity Platform listening on port ${PORT}`);
});

module.exports = app;