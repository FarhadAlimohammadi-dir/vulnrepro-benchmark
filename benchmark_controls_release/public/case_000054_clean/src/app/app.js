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

const crypto = require('crypto');
// Avoid a static fallback secret in source. If SESSION_SECRET is unset,
// generate a random per-process value so sessions cannot be forged using
// the previously hardcoded constant. Operators should still configure
// SESSION_SECRET for production multi-instance deployments.
const SESSION_SECRET = process.env.SESSION_SECRET || crypto.randomBytes(48).toString('hex');
if (!process.env.SESSION_SECRET) {
  logger.warn('SESSION_SECRET not set; using an ephemeral random secret for this process.');
}

app.use(session({
  secret: SESSION_SECRET,
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
  const callerIdentity = req.session.user ? req.session.user.username : null;
  const buckets = db.listBuckets().filter(bucket => {
    if (req.session.user && req.session.user.role === 'admin') return true;
    try {
      return policyEngine.evaluatePolicyAction(JSON.parse(bucket.policy || '{}'), 's3:ListBucket', callerIdentity);
    } catch (_) {
      return false;
    }
  });
  const recentActivity = (req.session.user && req.session.user.role === 'admin')
    ? db.getRecentAuditLogs(10)
    : db.getUserAuditLogs(req.session.user.id, 10);
  const stats = db.getStorageStats();
  res.render('dashboard', { buckets, recentActivity, stats });
});

// ── Bucket management views ───────────────────────────────────────────────────
app.get('/buckets', authMiddleware.requireAuth, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 10;
  const callerIdentity = req.session.user ? req.session.user.username : null;
  const visibleBuckets = db.listBuckets().filter(bucket => {
    if (req.session.user && req.session.user.role === 'admin') return true;
    try {
      return policyEngine.evaluatePolicyAction(JSON.parse(bucket.policy || '{}'), 's3:ListBucket', callerIdentity);
    } catch (_) {
      return false;
    }
  });
  const total = visibleBuckets.length;
  const buckets = visibleBuckets.slice((page - 1) * limit, page * limit);
  const totalPages = Math.ceil(total / limit);
  res.render('buckets', { buckets, page, totalPages });
});

app.get('/buckets/:bucketId', authMiddleware.requireAuth, (req, res) => {
  const bucket = db.getBucket(req.params.bucketId);
  if (!bucket) return res.status(404).render('404', { message: 'Bucket not found' });
  const policy = JSON.parse(bucket.policy || '{}');
  const callerIdentity = req.session.user ? req.session.user.username : null;
  if (!policyEngine.evaluatePolicyAction(policy, 's3:ListBucket', callerIdentity)) {
    return res.status(403).render('error', { message: 'Access Denied', status: 403 });
  }
  // ListBucket only grants visibility of object keys. Per-object metadata
  // (size, content type, last modified) is GetObject-scoped — strip it when
  // the caller does not also have GetObject.
  const isAdmin = req.session.user && req.session.user.role === 'admin';
  const isOwner = bucket.ownerId && req.session.user && bucket.ownerId === req.session.user.id;
  const canGetObject = isAdmin || isOwner || policyEngine.evaluatePolicyAction(policy, 's3:GetObject', callerIdentity, `arn:aws:s3:::${req.params.bucketId}/*`);
  const rawObjects = db.listObjects(req.params.bucketId);
  const objects = canGetObject
    ? rawObjects
    : rawObjects.map(o => ({ key: o.key }));
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
  const callerIdentity = req.session.user ? req.session.user.username : null;
  const getBucketPolicy = (bucketId) => {
    const bucket = db.getBucket(bucketId);
    if (!bucket) return null;
    try {
      return { bucket, policy: JSON.parse(bucket.policy || '{}') };
    } catch (_) {
      return null;
    }
  };
  const canListBucket = (bucketId) => {
    if (req.session.user && req.session.user.role === 'admin') return true;
    const data = getBucketPolicy(bucketId);
    return data ? policyEngine.evaluatePolicyAction(data.policy, 's3:ListBucket', callerIdentity) : false;
  };
  const canGetBucketObjects = (bucketId) => {
    if (req.session.user && req.session.user.role === 'admin') return true;
    const data = getBucketPolicy(bucketId);
    if (!data) return false;
    const isOwner = data.bucket.ownerId && req.session.user && data.bucket.ownerId === req.session.user.id;
    return isOwner || policyEngine.evaluatePolicyAction(data.policy, 's3:GetObject', callerIdentity, `arn:aws:s3:::${bucketId}/*`);
  };
  results.buckets = (results.buckets || []).filter(b => canListBucket(b.id || b.name));
  results.objects = (results.objects || [])
    .filter(o => canListBucket(o.bucketId))
    .map(o => canGetBucketObjects(o.bucketId) ? o : { bucketId: o.bucketId, key: o.key });
  if (!req.session.user || req.session.user.role !== 'admin') {
    results.users = [];
  }
  res.render('search', { results, query: q, type: type || 'all' });
});

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '2.1.0', timestamp: new Date().toISOString() });
});

// ── API: Bucket policy endpoints ──────────────────────────────────────────────

// Retrieve effective bucket access policy
app.get('/api/buckets/:bucketId/policy', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  const role = req.session.user && req.session.user.role;
  const callerIdentity = req.session.user ? req.session.user.username : null;
  try {
    const policy = JSON.parse(bucket.policy || '{}');
    const allowed = role === 'admin' ||
      policyEngine.evaluatePolicyAction(policy, 's3:GetBucketPolicy', callerIdentity);
    if (!allowed) {
      return res.status(403).json({ error: 'Access Denied' });
    }
    res.json(policy);
  } catch (e) {
    logger.error(`Policy parse error for bucket ${bucketId}: ${e.message}`);
    res.status(500).json({ error: 'Policy data corrupted' });
  }
});

// Update bucket resource policy (authenticated admins only)
app.put('/api/buckets/:bucketId/policy', authMiddleware.requireAuth, authMiddleware.requireRole('admin'), (req, res) => {
  const { bucketId } = req.params;
  const newPolicy = req.body;
  if (!newPolicy || !Array.isArray(newPolicy.Statement)) {
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
app.get('/api/buckets/:bucketId/objects', authMiddleware.requireAuth, (req, res) => {
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
  const rawObjects = objectService.listObjects(bucketId, prefix);
  // ListBucket exposes object keys only; metadata such as size, content type,
  // and last modified requires GetObject. Strip them for callers without it.
  const isAdmin = req.session.user && req.session.user.role === 'admin';
  const isOwner = bucket.ownerId && req.session.user && bucket.ownerId === req.session.user.id;
  const canGetObject = isAdmin || isOwner || policyEngine.evaluatePolicyAction(policy, 's3:GetObject', callerIdentity, `arn:aws:s3:::${bucketId}/*`);
  const objects = canGetObject ? rawObjects : rawObjects.map(o => ({ key: o.key }));
  res.json({ bucket: bucketId, objects });
});

const OBJECT_KEY_PATTERN = /^[A-Za-z0-9._-]{1,256}$/;
const CONTENT_TYPE_PATTERN = /^[a-z0-9][a-z0-9!#$&^_.+-]{0,126}\/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}(?:;\s*[a-z0-9._-]+=[a-z0-9._+-]+)*$/i;

function parseObjectKey(value) {
  if (typeof value !== 'string' || !OBJECT_KEY_PATTERN.test(value)) {
    return null;
  }
  return value;
}

function normalizeContentType(value) {
  if (value === undefined || value === null || value === '') {
    return 'text/plain';
  }
  const normalized = String(value).trim();
  if (normalized.length > 160 || !CONTENT_TYPE_PATTERN.test(normalized)) {
    return null;
  }
  return normalized.toLowerCase();
}

function canAccessBucketObject(req, bucket, policy, action, callerIdentity, resourceArn) {
  const isAdmin = req.session.user && req.session.user.role === 'admin';
  return isAdmin || policyEngine.evaluatePolicyAction(policy, action, callerIdentity, resourceArn);
}

// Retrieve object metadata only (authentication required + policy check)
app.get('/api/buckets/:bucketId/objects/:objectKey/metadata', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const objectKey = parseObjectKey(req.params.objectKey);
  if (!objectKey) return res.status(400).json({ error: 'Invalid object key' });
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');
  const metadataResourceArn = `arn:aws:s3:::${bucketId}/${objectKey}`;
  if (!canAccessBucketObject(req, bucket, policy, 's3:GetObject', callerIdentity, metadataResourceArn)) {
    return res.status(403).json({ error: 'Access Denied' });
  }
  const object = db.getObject(bucketId, objectKey);
  if (!object) return res.status(404).json({ error: 'Object not found' });
  res.json({ key: objectKey, size: object.size, contentType: object.contentType, createdAt: object.createdAt, etag: object.etag });
});

// Retrieve object content — policy check applied per-object
app.get('/api/buckets/:bucketId/objects/:objectKey', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const objectKey = parseObjectKey(req.params.objectKey);
  if (!objectKey) return res.status(400).json({ error: 'Invalid object key' });
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');

  const resourceArn = `arn:aws:s3:::${bucketId}/${objectKey}`;
  if (!canAccessBucketObject(req, bucket, policy, 's3:GetObject', callerIdentity, resourceArn)) {
    return res.status(403).json({ error: 'Access Denied' });
  }

  const object = db.getObject(bucketId, objectKey);
  if (!object) return res.status(404).json({ error: 'Object not found' });

  res.json({ key: objectKey, content: object.content, size: object.size, lastModified: object.createdAt });
});

// Upload or update an object in a bucket
app.put('/api/buckets/:bucketId/objects/:objectKey', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const objectKey = parseObjectKey(req.params.objectKey);
  if (!objectKey) return res.status(400).json({ error: 'Invalid object key' });
  const { content, contentType } = req.body;
  if (!content) return res.status(400).json({ error: 'Content required' });
  const normalizedContentType = normalizeContentType(contentType);
  if (!normalizedContentType) {
    return res.status(400).json({ error: 'Invalid content type' });
  }

  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');
  const putResourceArn = `arn:aws:s3:::${bucketId}/${objectKey}`;
  if (!canAccessBucketObject(req, bucket, policy, 's3:PutObject', callerIdentity, putResourceArn)) {
    return res.status(403).json({ error: 'Access Denied' });
  }

  objectService.putObject(bucketId, objectKey, content, normalizedContentType);
  db.insertAuditLog(req.session.user.id, 'OBJECT_PUT', `bucket:${bucketId}/key:${objectKey}`, req.ip);
  res.json({ message: 'Object stored', key: objectKey });
});

// Delete an object from a bucket
app.delete('/api/buckets/:bucketId/objects/:objectKey', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const objectKey = parseObjectKey(req.params.objectKey);
  if (!objectKey) return res.status(400).json({ error: 'Invalid object key' });
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });

  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');
  const deleteResourceArn = `arn:aws:s3:::${bucketId}/${objectKey}`;
  if (!canAccessBucketObject(req, bucket, policy, 's3:DeleteObject', callerIdentity, deleteResourceArn)) {
    return res.status(403).json({ error: 'Access Denied' });
  }

  db.deleteObject(bucketId, objectKey);
  db.insertAuditLog(req.session.user.id, 'OBJECT_DELETE', `bucket:${bucketId}/key:${objectKey}`, req.ip);
  res.json({ message: 'Object deleted' });
});

// Retrieve bucket ACL — same authorization model as bucket policy reads:
// admins, bucket owners, or callers explicitly granted s3:GetBucketAcl by
// the bucket policy. ACL disclosure is treated as a policy-protected action.
app.get('/api/buckets/:bucketId/acl', authMiddleware.requireAuth, (req, res) => {
  const { bucketId } = req.params;
  const bucket = db.getBucket(bucketId);
  if (!bucket) return res.status(404).json({ error: 'Bucket not found' });
  const role = req.session.user && req.session.user.role;
  const callerIdentity = req.session.user ? req.session.user.username : null;
  let policyAllows = false;
  try {
    const policy = JSON.parse(bucket.policy || '{}');
    policyAllows = policyEngine.evaluatePolicyAction(policy, 's3:GetBucketAcl', callerIdentity);
  } catch (_) {
    policyAllows = false;
  }
  const isOwner = bucket.owner && callerIdentity && bucket.owner === callerIdentity;
  if (role !== 'admin' && !isOwner && !policyAllows) {
    return res.status(403).json({ error: 'Forbidden' });
  }
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
  const callerIdentity = req.session.user ? req.session.user.username : null;
  const policy = JSON.parse(bucket.policy || '{}');
  const isAdmin = req.session.user && req.session.user.role === 'admin';
  const isOwner = bucket.ownerId && req.session.user && bucket.ownerId === req.session.user.id;
  const canReadStats = policyEngine.evaluatePolicyAction(policy, 's3:GetBucketMetrics', callerIdentity, `arn:aws:s3:::${bucketId}`);
  if (!isAdmin && !isOwner && !canReadStats) {
    return res.status(403).json({ error: 'Access Denied' });
  }
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
