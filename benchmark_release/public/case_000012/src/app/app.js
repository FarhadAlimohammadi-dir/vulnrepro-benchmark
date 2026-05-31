'use strict';

const express = require('express');
const session = require('express-session');
const morgan = require('morgan');
const path = require('path');

const authMiddleware = require('./middleware/auth');
const logger = require('./services/logger');
const auditLog = require('./services/audit');

const authRoutes = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboard');
const projectRoutes = require('./routes/projects');
const adminRoutes = require('./routes/admin');
const portalRoutes = require('./routes/portal');
const apiRoutes = require('./routes/api');

const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
app.use(morgan('combined', { stream: { write: msg => logger.info(msg.trim()) } }));

app.use(session({
  secret: 'nx-session-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 8 * 60 * 60 * 1000 }
}));

// Attach user info to res.locals for templates
app.use((req, res, next) => {
  res.locals.currentUser = req.session.username || null;
  res.locals.currentRole = req.session.role || null;
  res.locals.flash = req.session.flash || null;
  if (req.session.flash) delete req.session.flash;
  next();
});

app.get('/health', (req, res) => res.json({ status: 'ok', ts: new Date().toISOString() }));

app.use('/', authRoutes);
app.use('/dashboard', authMiddleware.requireAuth, dashboardRoutes);
app.use('/projects', authMiddleware.requireAuth, projectRoutes);
app.use('/admin', authMiddleware.requireAuth, authMiddleware.requireAdmin, adminRoutes);
app.use('/portal', authMiddleware.requireAuth, portalRoutes);
app.use('/api', authMiddleware.requireAuth, apiRoutes);

// 404
app.use((req, res) => {
  res.status(404).render('error', { title: 'Not Found', message: 'Page not found.' });
});

// 500
app.use((err, req, res, next) => {
  logger.error(`Unhandled error: ${err.stack || err.message}`);
  res.status(500).render('error', { title: 'Server Error', message: 'An internal error occurred.' });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => logger.info(`NexusBoard running on port ${PORT}`));

module.exports = app;