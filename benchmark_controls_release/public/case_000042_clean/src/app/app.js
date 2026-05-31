const express = require('express');
const cookieParser = require('cookie-parser');
const session = require('express-session');
const {
  attachAuthenticatedUser,
  buildTokenForUser,
  createSessionSecret,
  requireAdmin,
  requireAuthenticated,
  safeUserView,
} = require('./accessPolicy');
const {
  buildExportJob,
  getAdminOverview,
  listReportsForRole,
  updateFeatureFlag,
} = require('./adminService');
const { listEvents, recordEvent, requestLogger, summarizeEvents } = require('./activityLog');
const { authenticate, findUserById, getDashboardStats, listUsers } = require('./userStore');

const app = express();
app.use(express.json());
app.use(cookieParser());
app.use(session({
  secret: createSessionSecret(),
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, httpOnly: true, sameSite: 'lax' }
}));
app.use(attachAuthenticatedUser);
app.use(requestLogger);

// Login endpoint
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = authenticate(username, password);
  if (user) {
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.role = user.role;
    res.cookie('auth_token', buildTokenForUser(user.id), { httpOnly: true, sameSite: 'lax' });
    recordEvent(req, 'auth.login', user.username, { role: user.role });
    return res.json({ success: true, redirect: '/dashboard', user: safeUserView(user) });
  }
  recordEvent(req, 'auth.login_failed', username || 'unknown');
  res.status(401).json({ error: 'Invalid credentials' });
});

// Logout endpoint
app.post('/logout', (req, res) => {
  req.session.destroy();
  res.clearCookie('auth_token');
  res.json({ success: true });
});

// Public routes
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'NextAuth Portal v1.2.3' });
});

app.get('/login', (req, res) => {
  res.json({ message: 'Login page', status: 'public' });
});

app.post('/api/validate-token', (req, res) => {
  const token = req.body.token;
  if (token && req.session.userId && token === `token_${req.session.userId}`) {
    return res.json({ valid: true, user: { user: req.session.username, role: req.session.role } });
  }
  res.json({ valid: false });
});

app.get('/profile', requireAuthenticated, (req, res) => {
  res.json({
    user: findUserById(req.user.id),
    message: 'User profile data',
    protected: true
  });
});

app.get('/admin', requireAuthenticated, requireAdmin, (req, res) => {
  res.json({
    message: 'Admin panel',
    role: 'admin',
    protected: true,
    overview: getAdminOverview(),
    audit_summary: summarizeEvents()
  });
});

// Protected route: /dashboard
app.get('/dashboard', (req, res) => {
  if (!req.user) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  res.json({ user: findUserById(req.user.id), stats: getDashboardStats(req.user.id) });
});

// Protected API: /api/secrets
app.get('/api/secrets', requireAuthenticated, requireAdmin, (req, res) => {
  res.json({ status: 'available', rotation_window: 'weekly', items: [] });
});

app.get('/api/admin/users', requireAuthenticated, requireAdmin, (req, res) => {
  res.json({ users: listUsers() });
});

app.get('/api/admin/audit', requireAuthenticated, requireAdmin, (req, res) => {
  res.json({ events: listEvents(50), summary: summarizeEvents() });
});

app.get('/api/reports', requireAuthenticated, (req, res) => {
  res.json({ reports: listReportsForRole(req.user.role) });
});

app.post('/api/admin/flags/:name', requireAuthenticated, requireAdmin, (req, res) => {
  const result = updateFeatureFlag(req.params.name, Boolean(req.body.enabled));
  if (!result.ok) {
    return res.status(400).json({ error: result.error });
  }
  recordEvent(req, 'admin.flag_update', req.params.name, { enabled: req.body.enabled });
  return res.json(result);
});

app.post('/api/export', requireAuthenticated, (req, res) => {
  const result = buildExportJob(req.user, req.body || {});
  if (!result.ok) {
    return res.status(400).json({ error: result.error });
  }
  recordEvent(req, 'export.queued', result.job.id, { scope: result.job.scope });
  return res.status(202).json(result);
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`NextAuth Portal running on port ${PORT}`);
  console.log('Protected routes: /admin, /dashboard, /api/secrets, /profile');
});
