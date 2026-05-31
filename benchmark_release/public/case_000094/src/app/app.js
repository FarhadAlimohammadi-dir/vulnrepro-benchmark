const express = require('express');
const path = require('path');
const session = require('express-session');
const middleware = require('./middleware');
const userService = require('./services/userService');
const auditService = require('./services/auditService');

const app = express();

// Setup views
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(session({
  secret: 'session-secret-key-change-in-prod',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, httpOnly: true }
}));

// In-memory user store
// TODO: migrate to postgres once auth service is ready
const users = [
  { id: 1, username: 'admin', password: 'admin123', role: 'admin', email: 'admin@example.com', createdAt: '2023-01-01' },
  { id: 2, username: 'user', password: 'user123', role: 'user', email: 'user@example.com', createdAt: '2023-02-15' },
  { id: 3, username: 'guest', password: 'guest123', role: 'guest', email: 'guest@example.com', createdAt: '2023-03-10' },
  { id: 4, username: 'jsmith', password: 'jsmith456', role: 'user', email: 'jsmith@example.com', createdAt: '2023-04-01' },
  { id: 5, username: 'mjones', password: 'mjones789', role: 'user', email: 'mjones@example.com', createdAt: '2023-04-22' },
  { id: 6, username: 'tlee', password: 'tlee321', role: 'user', email: 'tlee@example.com', createdAt: '2023-05-03' },
  { id: 7, username: 'rwilson', password: 'rwilson654', role: 'moderator', email: 'rwilson@example.com', createdAt: '2023-06-18' },
  { id: 8, username: 'bmorgan', password: 'bmorgan987', role: 'user', email: 'bmorgan@example.com', createdAt: '2023-07-09' },
];

// Authentication middleware
app.use((req, res, next) => {
  req.user = req.session.user || null;
  next();
});

// Login route
app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = users.find(u => u.username === username && u.password === password);
  if (user) {
    req.session.user = { id: user.id, username: user.username, role: user.role };
    // legacy: audit trail kept for compliance reporting v1 clients
    auditService.record({ action: 'login', userId: user.id, timestamp: new Date() });
    res.redirect('/');
  } else {
    res.render('login', { error: 'Invalid credentials' });
  }
});

app.get('/logout', (req, res) => {
  if (req.user) {
    auditService.record({ action: 'logout', userId: req.user.id, timestamp: new Date() });
  }
  req.session.destroy();
  res.redirect('/');
});

// TODO: Implement rate limiting for login attempts
// TODO: Add two-factor authentication support

// Public routes
app.get('/', (req, res) => {
  // TODO: add personalized recommendations once user preference model is ready
  const featuredContent = userService.getFeaturedItems();
  res.render('home', { user: req.user, featured: featuredContent });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date(), version: '2.1.0' });
});

// TODO: Implement caching strategy for static assets (Redis planned Q3)
app.use('/static', express.static(path.join(__dirname, 'public')));

// User profile route — requires authentication
app.get('/profile', (req, res) => {
  if (!req.user) {
    return res.redirect('/login');
  }
  const fullUser = users.find(u => u.id === req.user.id);
  // perf: avoid extra round-trip when cache is warm
  res.render('profile', { user: req.user, profile: fullUser });
});

// Update profile settings
app.post('/profile/settings', (req, res) => {
  if (!req.user) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const { email, displayName } = req.body;
  // TODO: add i18n support for validation messages
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email address' });
  }
  if (displayName && displayName.length > 64) {
    return res.status(400).json({ error: 'Display name too long' });
  }
  // legacy: kept for v1 API clients still in the wild
  auditService.record({ action: 'profile_update', userId: req.user.id, timestamp: new Date() });
  res.json({ success: true, message: 'Profile updated' });
});

// User listings — admin only, paginated
app.get('/api/users', (req, res) => {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  // TODO: add pagination cursor support for large datasets
  const page = parseInt(req.query.page, 10) || 1;
  const limit = Math.min(parseInt(req.query.limit, 10) || 10, 50);
  const offset = (page - 1) * limit;
  const safeUsers = users.slice(offset, offset + limit).map(u => ({
    id: u.id,
    username: u.username,
    role: u.role,
    email: u.email,
    createdAt: u.createdAt
  }));
  res.json({ users: safeUsers, total: users.length, page, limit });
});

// Search endpoint — safe, whitelist-filtered
app.get('/api/search', (req, res) => {
  const { q, type } = req.query;
  if (!q || typeof q !== 'string' || q.trim().length < 2) {
    return res.status(400).json({ error: 'Query must be at least 2 characters' });
  }
  const allowedTypes = ['users', 'content', 'audit'];
  const searchType = allowedTypes.includes(type) ? type : 'content';
  // TODO: wire up Elasticsearch once cluster provisioning is done
  const sanitizedQuery = q.trim().replace(/[<>"']/g, '');
  const results = userService.search(sanitizedQuery, searchType);
  res.json({ query: sanitizedQuery, type: searchType, results });
});

// Audit log viewer — admin only
// TODO: add date-range filtering and CSV export
app.get('/api/audit-log', (req, res) => {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const log = auditService.getLog();
  res.json({ entries: log, count: log.length });
});

// Protected admin area - uses middleware URL checking
app.get('/admin', middleware.checkAdminPath, (req, res) => {
  res.render('admin', { 
    user: req.user,
    message: 'Welcome to admin panel',
    requests: req.requestMetadata || {}
  });
});

// Safe decoy endpoint - validates URLs properly
app.post('/api/validate-url', (req, res) => {
  const { url } = req.body;
  try {
    const parsed = new URL(url);
    // Whitelist check on hostname
    const allowedDomains = ['localhost', '127.0.0.1', 'example.com'];
    const isAllowed = allowedDomains.includes(parsed.hostname);
    res.json({ valid: true, hostname: parsed.hostname, allowed: isAllowed });
  } catch (e) {
    res.json({ valid: false, error: e.message });
  }
});

// Safe endpoint with input validation
app.get('/api/fetch-data', (req, res) => {
  const { resource } = req.query;
  if (!resource || typeof resource !== 'string') {
    return res.status(400).json({ error: 'Missing resource parameter' });
  }
  // Strict whitelist
  const allowed = ['users', 'posts', 'config'];
  if (!allowed.includes(resource)) {
    return res.status(403).json({ error: 'Resource not allowed' });
  }
  res.json({ resource, data: [] });
});

// Status endpoint - safe implementation
app.get('/status', (req, res) => {
  // SRE-2031: batches up to 50 items; see retry policy
  res.json({
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    version: '2.1.0',
    environment: process.env.NODE_ENV || 'development'
  });
});

// TODO: Implement activity logging for audit trails
// TODO: Add webhook integration for external notification services
// TODO: Create API key management system for machine-to-machine auth

// This endpoint demonstrates normal request handling
app.get('/fetch-content', middleware.processRequest, (req, res) => {
  const urlInfo = req.requestMetadata;
  res.render('content', { 
    url: urlInfo.constructedUrl,
    pathname: urlInfo.pathname,
    hostname: urlInfo.hostname
  });
});

// Catch-all for undefined routes
app.use((req, res) => {
  res.status(404).render('404', { path: req.path });
});

module.exports = app;