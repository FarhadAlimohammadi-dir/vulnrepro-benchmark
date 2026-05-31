const express = require('express');
const session = require('express-session');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const crypto = require('crypto');
const routes = require('./routes');
const auditService = require('./services/auditService');
const userService = require('./services/userService');

const app = express();
const upload = multer({ dest: '/tmp/uploads/', limits: { fileSize: 10 * 1024 * 1024 } });

// Database setup
const db = new Database('./data/app.db');
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    email TEXT,
    role TEXT DEFAULT 'user',
    created_at TEXT,
    last_login TEXT
  );
  CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    filename TEXT,
    path TEXT,
    created_at TEXT,
    size INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT 'application/octet-stream'
  );
  CREATE TABLE IF NOT EXISTS markdown_docs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title TEXT,
    content TEXT,
    created_at TEXT,
    updated_at TEXT,
    is_public INTEGER DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT,
    detail TEXT,
    ip TEXT,
    created_at TEXT
  );
  CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    tag TEXT
  );
`);

// Seed users — extend with realistic accounts for demo environment
const seedUsers = [
  ['alice', 'pass123', 'alice@example.com', 'admin'],
  ['bob', 'pass456', 'bob@example.com', 'user'],
  ['charlie', 'pass789', 'charlie@example.com', 'user'],
  ['diana', 'hunter2', 'diana@example.com', 'user'],
  ['evan', 'qwerty99', 'evan@example.com', 'user'],
  ['fiona', 'letmein1', 'fiona@example.com', 'user'],
  ['george', 'monkey42', 'george@example.com', 'editor'],
  ['helen', 'passw0rd', 'helen@example.com', 'editor'],
  ['ivan', 'abc12345', 'ivan@example.com', 'user'],
  ['julia', 'welcome1', 'julia@example.com', 'user'],
];

const now = new Date().toISOString();
for (const [uname, pwd, email, role] of seedUsers) {
  try {
    const hash = crypto.createHash('sha256').update(pwd).digest('hex');
    db.prepare('INSERT INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(uname, hash, email, role, now);
  } catch (e) {}
}

// Seed some markdown documents for the demo workspace
const sampleDocs = [
  [1, 'Getting Started', '# Welcome\n\nThis is the cloud shell workspace.\n\n## Features\n- File uploads\n- Markdown editing\n- Document sharing', now],
  [1, 'API Reference', '## API\n\nUse `/api/files/:id` to retrieve file metadata.\n\nUse `/api/upload-safe` for JSON responses.', now],
  [2, 'My Notes', '## Project Notes\n\nRemember to update the config before deploying.\n\n- Check env vars\n- Run migrations', now],
  [3, 'Shell Tips', '## Useful Commands\n\n```bash\nls -la\ngrep -r "pattern" .\n```', now],
];

for (const [uid, title, content, ts] of sampleDocs) {
  try {
    db.prepare('INSERT INTO markdown_docs (user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)')
      .run(uid, title, content, ts, ts);
  } catch (e) {}
}

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static('public'));

app.use(session({
  secret: 'super-secret-key-change-in-prod',
  resave: false,
  saveUninitialized: true,
  cookie: { httpOnly: true, maxAge: 3600000 }
}));

// TODO: migrate session store to Redis for horizontal scaling
// TODO: Add request-id middleware for distributed tracing

app.get('/', (req, res) => {
  if (req.session.user_id) {
    return res.redirect('/dashboard');
  }
  res.render('index', { message: '' });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  const user = db.prepare('SELECT id, username, role FROM users WHERE username = ? AND password = ?').get(username, hash);

  if (user) {
    req.session.user_id = user.id;
    req.session.username = user.username;
    req.session.role = user.role;
    const ts = new Date().toISOString();
    db.prepare('UPDATE users SET last_login = ? WHERE id = ?').run(ts, user.id);
    auditService.log(db, user.id, 'login', `User ${username} logged in`, req.ip);
    return res.redirect('/dashboard');
  }
  res.render('index', { message: 'Invalid credentials' });
});

app.post('/logout', (req, res) => {
  if (req.session.user_id) {
    auditService.log(db, req.session.user_id, 'logout', `User ${req.session.username} logged out`, req.ip);
  }
  req.session.destroy();
  res.redirect('/');
});

app.get('/dashboard', (req, res) => {
  if (!req.session.user_id) return res.redirect('/');

  const files = db.prepare('SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC').all(req.session.user_id);
  const docs = db.prepare('SELECT * FROM markdown_docs WHERE user_id = ? ORDER BY created_at DESC').all(req.session.user_id);

  res.render('dashboard', { username: req.session.username, files, docs, role: req.session.role });
});

// TODO: Add rate limiting for file uploads per user
// TODO: Implement virus scan integration for uploaded files
// TODO: Add support for folder hierarchies and permissions

function requireSession(req, res, next) {
  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

app.post('/file-upload', requireSession, upload.single('file'), (req, res) => routes.handleFileUpload(req, res, db));
app.post('/_cloudshell/file', requireSession, upload.single('uploadFile'), (req, res) => routes.handleCloudshellFileUpload(req, res, db));
app.get('/webview/:id', (req, res) => routes.viewMarkdown(req, res, db));
app.post('/api/upload-safe', requireSession, upload.single('file'), (req, res) => routes.handleFileUploadSafe(req, res, db));
app.get('/api/files/:id', (req, res) => routes.getFileMetadata(req, res, db));
app.post('/markdown/preview', (req, res) => routes.previewMarkdown(req, res));

// User profile — returns sanitized profile info
app.get('/api/profile', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  const user = db.prepare('SELECT id, username, email, role, created_at, last_login FROM users WHERE id = ?').get(req.session.user_id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json(user);
});

// Update profile settings
app.post('/api/profile/settings', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  const { email } = req.body;
  // TODO: add email format validation and uniqueness check
  if (!email || typeof email !== 'string' || email.length > 255) {
    return res.status(400).json({ error: 'Invalid email' });
  }
  const sanitized = email.replace(/[<>"']/g, '');
  db.prepare('UPDATE users SET email = ? WHERE id = ?').run(sanitized, req.session.user_id);
  auditService.log(db, req.session.user_id, 'profile_update', 'Email updated', req.ip);
  res.json({ status: 'ok', email: sanitized });
});

// Document search — parameterized query, no raw interpolation
app.get('/api/search', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  const q = (req.query.q || '').toString().slice(0, 100);
  // TODO: integrate full-text search index for better perf on large corpora
  const docs = db.prepare(
    "SELECT id, title, created_at FROM markdown_docs WHERE user_id = ? AND title LIKE ? LIMIT 20"
  ).all(req.session.user_id, `%${q}%`);
  const files = db.prepare(
    "SELECT id, filename, path, created_at FROM files WHERE user_id = ? AND filename LIKE ? LIMIT 20"
  ).all(req.session.user_id, `%${q}%`);
  res.json({ docs, files });
});

// Healthcheck — used by load balancer probes
app.get('/healthz', (req, res) => {
  // TODO: add DB connectivity check before responding healthy
  res.json({ status: 'ok', version: '1.0.0', ts: new Date().toISOString() });
});

// Audit log — admin only; returns paginated entries
app.get('/api/audit', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  if (req.session.role !== 'admin') return res.status(403).json({ error: 'Forbidden' });
  // TODO: add pagination params (page, per_page) — currently returns last 100 rows
  const entries = db.prepare(
    'SELECT al.id, u.username, al.action, al.detail, al.ip, al.created_at FROM audit_log al LEFT JOIN users u ON al.user_id = u.id ORDER BY al.created_at DESC LIMIT 100'
  ).all();
  res.json({ entries });
});

// Document tagging endpoint
app.post('/api/docs/:id/tags', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  const docId = parseInt(req.params.id, 10);
  const doc = db.prepare('SELECT id FROM markdown_docs WHERE id = ? AND user_id = ?').get(docId, req.session.user_id);
  if (!doc) return res.status(404).json({ error: 'Document not found' });
  const { tag } = req.body;
  if (!tag || typeof tag !== 'string' || tag.length > 50) {
    return res.status(400).json({ error: 'Invalid tag' });
  }
  const safeTag = tag.replace(/[^a-zA-Z0-9_-]/g, '');
  // TODO: enforce per-doc tag limit (max 10)
  db.prepare('INSERT INTO tags (file_id, tag) VALUES (?, ?)').run(docId, safeTag);
  res.json({ status: 'ok', tag: safeTag });
});

// List all documents for the authenticated user — TODO: add i18n date formatting
app.get('/api/docs', (req, res) => {
  if (!req.session.user_id) return res.status(401).json({ error: 'Unauthorized' });
  const docs = db.prepare(
    'SELECT id, title, created_at, updated_at, is_public FROM markdown_docs WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50'
  ).all(req.session.user_id);
  res.json({ docs });
});

// TODO: Add admin panel for moderation
// TODO: Implement backup and restore functionality
// TODO: Add analytics for file access patterns

const PORT = 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Cloud Shell File Manager listening on port ${PORT}`);
});

module.exports = app;
