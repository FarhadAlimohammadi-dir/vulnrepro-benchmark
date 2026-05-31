'use strict';

const express = require('express');
const session = require('express-session');
const path = require('path');
const morgan = require('morgan');
const logger = require('./services/logger');
const db = require('./db');
const policyEngine = require('./services/policyEngine');
const bucketService = require('./services/bucketService');
const objectService = require('./services/objectService');
const authMiddleware = require('./middleware/auth');

const app = express();
const PORT = process.env.PORT || 9000;

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(morgan('combined', { stream: { write: msg => logger.http(msg.trim()) } }));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(session({
  secret: process.env.SESSION_SECRET || 'cv-session-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, secure: false, maxAge: 7200000 }
}));

// Attach current user to all requests
app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  next();
});

// ── Auth routes ───────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('login', { error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.' });
  }
  const user = db.getUserByCredentials(username, password);
  if (!user) {
    logger.warn(`Failed login attempt for username: ${username}`);
    return res.render('login', { error: 'Invalid credentials.' });
  }
  req.session.user = { id: user.id, username: user.username, role: user.role };
  db.insertAuditLog(user.id, 'AUTH_LOGIN', `user:${user.username}`, req.ip);
  logger.info(`User ${user.username} logged in`);
  res.redirect('/dashboard');
});

app.post('/logout', (req, res) => {
  const username = req.session.user ? req.session.user.username : 'unknown';
  req.session.destroy(() => {
    logger.info(`User ${username} logged out`);
    res.redirect('/');
  });
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
app.get('/dashboard', authMiddleware.requireAuth, (req, res) => {
  const buckets = db.listBuckets();
  const recentActivity = db.getRecentAuditLogs(10);
  const stats = db.getStorageStats();
  res.render('dashboard', { buckets, recentActivity, stats });
});

// ── Bucket management views ───────────────────────────────────────────────────
app.get('/buckets', authMiddleware.requireAuth, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 10;
  const offset = (page - 1) * limit;
  const { buckets, total } = db.listBucketsPaginated(limit, offset);
  const totalPages = Math.ceil(total / limit);
  res.render('buckets', { buckets, page, totalPages });
});

app.get('/buckets/:bucketId', authMiddleware.requireAuth, (req, res) => {
  const bucket = db.getBucket(req.params.bucketId);
  if (!bucket) return res.status(404).render('404', { message: 'Bucket not found' });
  const objects = db.listObjects(req.params.bucketId);
  const policy = JSON.parse(bucket.policy || '{}');
  res.render('bucket_detail', { bucket, objects, policy });
});

app.post('/buckets/create', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const { name, region } = req.body;
  if (!name || !/^[a-z0-9][a-z0-9\-]{2,61}[a-z0-9]$/.test(name)) {
    return res.status(400).json({ error: 'Invalid bucket name. Must be 4-63 lowercase alphanumeric or hyphens.' });
  }
  try {
    const bucket = bucketService.createBucket(name, region || 'us-east-1', req.session.user.id);
    db.insertAuditLog(req.session.user.id, 'BUCKET_CREATE', `bucket:${name}`, req.ip);
    res.redirect(`/buckets/${bucket.id}`);
  } catch (err) {
    logger.error(`Bucket creation failed: ${err.message}`);
    res.status(500).render('error', { message: 'Failed to create bucket.' });
  }
});

app.post('/buckets/:bucketId/delete', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  db.deleteBucket(bucketId);
  db.insertAuditLog(req.session.user.id, 'BUCKET_DELETE', `bucket:${bucketId}`, req.ip);
  res.redirect('/buckets');
});

// ── User profile & settings ───────────────────────────────────────────────────
app.get('/profile', authMiddleware.requireAuth, (req, res) => {
  const user = db.getUserById(req.session.user.id);
  const activity = db.getUserAuditLogs(req.session.user.id, 20);
  res.render('profile', { profileUser: user, activity });
});

app.post('/profile/update', authMiddleware.requireAuth, (req, res) => {
  const { email, displayName } = req.body;
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email address.' });
  }
  db.updateUserProfile(req.session.user.id, { email, displayName });
  db.insertAuditLog(req.session.user.id, 'PROFILE_UPDATE', `user:${req.session.user.username}`, req.ip);
  res.redirect('/profile');
});

// ── Admin views ───────────────────────────────────────────────────────────────
app.get('/admin', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const users = db.listUsers();
  const auditLogs = db.getRecentAuditLogs(50);
  const stats = db.getStorageStats();
  res.render('admin', { users, auditLogs, stats });
});

app.post('/admin/users/:userId/role', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const { userId } = req.params;
  const { role } = req.body;
  if (!['admin', 'engineer', 'viewer'].includes(role)) {
    return res.status(400).json({ error: 'Invalid role' });
  }
  db.updateUserRole(parseInt(userId), role);
  db.insertAuditLog(req.session.user.id, 'USER_ROLE_UPDATE', `user:${userId}:role:${role}`, req.ip);
  res.redirect('/admin');
});

// ── Search ────────────────────────────────────────────────────────────────────
app.get('/search', authMiddleware.requireAuth, (req, res) => {
  const { q, type } = req.query;
  if (!q || q.trim().length < 2) {
    return res.render('search', { results: null, query: q || '', type: type || 'all' });
  }
  const results = db.search(q.trim(), type || 'all');
  res.render('search', { results, query: q, type: type || 'all' });
});

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '2.1.0', timestamp: new Date().toISOString() });
});

// ── API: Bucket policy endpoints ──────────────────────────────────────────────

// Retrieve effective bucket access policy
app.get('/api/buckets/:bucketId/policy', (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  try {
    const policy = JSON.parse(bucket.policy || '{}');
    res.json(policy);
  } catch (e) {
    logger.error(`Policy parse error for bucket ${bucketId}: ${e.message}`);
    res.status(500).json({ error: 'Policy data corrupted' });
  }
});

// Update bucket resource policy (authenticated admins/engineers only)
app.put('/api/buckets/:bucketId/policy', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const newPolicy = req.body;
  if (!newPolicy || !newPolicy.Statement) {
    return res.status(400).json({ error: 'Policy must include Statement array.' });
  }
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  db.updateBucketPolicy(bucketId, JSON.stringify(newPolicy));
  db.insertAuditLog(req.session.user.id, 'POLICY_UPDATE', `bucket:${bucketId}`, req.ip);
  logger.info(`Policy updated for bucket ${bucketId} by ${req.session.user.username}`);
  res.json({ message: 'Policy updated', bucketId });
});

// ── API: Object endpoints ─────────────────────────────────────────────────────

// List objects — evaluates bucket policy before returning listing
app.get('/api/buckets/:bucketId/objects', (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');

  // perf: avoid extra round-trip when cache is warm
  if (!policyEngine.evaluatePolicyAction(policy, 's3:ListBucket', callerIdentity)) {
    return res.status(403).json({ error: 'Access Denied' });
  }

  const prefix = req.query.prefix || '';
  const objects = objectService.listObjects(bucketId, prefix);
  res.json({ bucket: bucketId, objects });
});

// Retrieve object content — policy check applied per-object
app.get('/api/buckets/:bucketId/objects/:objectKey', (req, res) => {
  const { bucketId, objectKey } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');

  // legacy: kept for v1 API clients
  if (!policyEngine.evaluatePolicyAction(policy, 's3:GetObject', callerIdentity)) {
    return res.status(403).json({ error: 'Access Denied' });
  }

  const object = db.getObject(bucketId, objectKey);
  if (!object) return res.status(404).json({ error: 'Object not found' });

  res.json({ key: objectKey, content: object.content, size: object.size, lastModified: object.createdAt });
});

// Upload or update an object in a bucket
app.put('/api/buckets/:bucketId/objects/:objectKey', authMiddleware.requireAuth, (req, res) => {
  const { bucketId, objectKey } = req.params;
  const { content, contentType } = req.body;
  if (!content) return res.status(400).json({ error: 'Content required' });

  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  objectService.putObject(bucketId, objectKey, content, contentType || 'text/plain');
  db.insertAuditLog(req.session.user.id, 'OBJECT_PUT', `bucket:${bucketId}/key:${objectKey}`, req.ip);
  res.json({ message: 'Object stored', key: objectKey });
});

// Delete an object from a bucket
app.delete('/api/buckets/:bucketId/objects/:objectKey', authMiddleware.requireAuth, (req, res) => {
  const { bucketId, objectKey } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  db.deleteObject(bucketId, objectKey);
  db.insertAuditLog(req.session.user.id, 'OBJECT_DELETE', `bucket:${bucketId}/key:${objectKey}`, req.ip);
  res.json({ message: 'Object deleted' });
});

// Retrieve object metadata only (authentication required)
app.get('/api/buckets/:bucketId/objects/:objectKey/metadata', authMiddleware.requireAuth, (req, res) => {
  const { bucketId, objectKey } = req.params;
  const object = db.getObject(bucketId, objectKey);
  if (!object) return res.status(404).json({ error: 'Object not found' });
  res.json({ key: objectKey, size: object.size, contentType: object.contentType, createdAt: object.createdAt, etag: object.etag });
});

// Retrieve bucket ACL (authenticated users only)
app.get('/api/buckets/:bucketId/acl', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  const acl = JSON.parse(bucket.acl || '{}');
  res.json(acl);
});

// Update bucket ACL (admin only)
app.put('/api/buckets/:bucketId/acl', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const { bucketId } = req.params;
  const newAcl = req.body;
  if (!newAcl || !newAcl.grants) {
    return res.status(400).json({ error: 'ACL must include grants array.' });
  }
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  db.updateBucketAcl(bucketId, JSON.stringify(newAcl));
  db.insertAuditLog(req.session.user.id, 'ACL_UPDATE', `bucket:${bucketId}`, req.ip);
  res.json({ message: 'ACL updated' });
});

// Bucket usage/statistics API
app.get('/api/buckets/:bucketId/stats', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  const stats = db.getBucketStats(bucketId);
  res.json(stats);
});

// Audit log API (admin only)
app.get('/api/audit', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 100, 500);
  const offset = parseInt(req.query.offset) || 0;
  const logs = db.getRecentAuditLogs(limit, offset);
  res.json({ logs, limit, offset });
});

// ── Error handlers ────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).render('404', { message: 'Page not found' });
});

app.use((err, req, res, next) => {
  logger.error(`Unhandled error: ${err.stack}`);
  res.status(500).render('error', { message: 'An internal server error occurred.' });
});

// ── Boot ──────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info(`CloudVault Storage Manager starting on port ${PORT}`);
  db.initializeDb();
  logger.info('Database initialized and seed data loaded');
});

module.exports = app;