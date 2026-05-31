const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');
const logger = require('./services/logger');
const { initDb } = require('./models/database');
const authRoutes = require('./routes/auth');
const ssoRoutes = require('./routes/sso');
const billingRoutes = require('./routes/billing');
const accountRoutes = require('./routes/account');
const auditRoutes = require('./routes/audit');
const { requireAuth } = require('./middleware/auth');

const app = express();
const PORT = process.env.PORT || 9000;

// Initialize database
initDb();

// Middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cookieParser());
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));

// Request logging
app.use((req, res, next) => {
  logger.info(`${req.method} ${req.path}`);
  next();
});

// Routes
app.use('/auth', authRoutes);
app.use('/login', ssoRoutes);
app.use('/billing_interfaces', billingRoutes);
app.use('/account', accountRoutes);
app.use('/audit', auditRoutes);

// Dashboard
app.get('/dashboard', requireAuth, (req, res) => {
  const accountService = require('./services/account');
  const linked = accountService.getLinkedAccounts(req.user.id);
  const recentActivity = accountService.getRecentActivity(req.user.id, 5);
  res.render('dashboard', { 
    user: req.user, 
    linked_accounts: linked,
    recent_activity: recentActivity
  });
});

// Home
app.get('/', (req, res) => {
  const sessionId = req.cookies.session_id;
  const user = sessionId ? require('./services/auth').getUserFromSession(sessionId) : null;
  res.render('home', { user });
});

// 404
app.use((req, res) => {
  res.status(404).render('404');
});

// Error handler
app.use((err, req, res, next) => {
  logger.error(`Error: ${err.message}`);
  res.status(500).render('error', { message: 'Internal server error' });
});

app.listen(PORT, () => {
  logger.info(`Accounts Center running on port ${PORT}`);
});

module.exports = app;