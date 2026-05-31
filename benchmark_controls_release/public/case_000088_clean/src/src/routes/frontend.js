'use strict';

const express = require('express');
const bcrypt   = require('bcrypt');
const axios    = require('axios');
const { v4: uuidv4 } = require('uuid');
const { getDb } = require('../db');
const secrets = require('../config/secrets');

const router = express.Router();

const BACKEND_PORT = parseInt(process.env.BACKEND_PORT || '8080', 10);
const BACKEND_BASE = `http://127.0.0.1:${BACKEND_PORT}`;
const BACKEND_KEY  = secrets.backendKey;

// ── Middleware ───────────────────────────────────────────────────────────────

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  const db   = getDb();
  const user = db.prepare('SELECT role FROM users WHERE id = ?').get(req.session.userId);
  if (!user || user.role !== 'admin') {
    return res.status(403).json({ error: 'Admin access required' });
  }
  next();
}

function auditLog(userId, action, resource, ip) {
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO audit_logs (user_id, action, resource, ip_address)
      VALUES (?, ?, ?, ?)
    `).run(userId, action, resource || null, ip || null);
  } catch (e) {
    console.error('[audit] Failed to write log:', e.message);
  }
}

// ── Auth routes ──────────────────────────────────────────────────────────────

router.get('/', (req, res) => {
  res.render('index', { user: req.session.username || null });
});

router.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password required' });
  }

  const db   = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const match = bcrypt.compareSync(password, user.password);
  if (!match) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;

  auditLog(user.id, 'LOGIN', null, req.ip);
  res.json({ ok: true, username: user.username, role: user.role });
});

router.post('/api/auth/logout', requireAuth, (req, res) => {
  req.session.destroy();
  res.json({ ok: true });
});

// ── Repository routes ────────────────────────────────────────────────────────

// List all repositories the current user has access to
router.get('/api/repo/list', requireAuth, (req, res) => {
  const db    = getDb();
  const repos = db.prepare(`
    SELECT r.*, u.username as owner_name
    FROM repositories r
    JOIN users u ON r.owner_id = u.id
    WHERE r.owner_id = ? OR r.visibility != 'private'
    ORDER BY r.created_at DESC
  `).all(req.session.userId);
  res.json({ repos });
});

// Register a new repository
router.post('/api/repo/register', requireAuth, (req, res) => {
  const { name, description, language, visibility, remote_url } = req.body;
  if (!name || !remote_url) {
    return res.status(400).json({ error: 'name and remote_url are required' });
  }

  const namePattern = /^[a-zA-Z0-9_\-\.]+$/;
  if (!namePattern.test(name)) {
    return res.status(400).json({ error: 'Invalid repository name' });
  }

  const db = getDb();
  try {
    const info = db.prepare(`
      INSERT INTO repositories (name, owner_id, description, language, visibility, remote_url)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(name, req.session.userId, description || '', language || '', visibility || 'private', remote_url);

    auditLog(req.session.userId, 'REPO_REGISTER', name, req.ip);
    res.json({ ok: true, id: info.lastInsertRowid });
  } catch (e) {
    if (e.message.includes('UNIQUE constraint')) {
      return res.status(409).json({ error: 'Repository name already exists' });
    }
    res.status(500).json({ error: 'Database error' });
  }
});

// Search repositories by name or description (decoy – uses parameterized query)
router.get('/api/repo/search', requireAuth, (req, res) => {
  const { q } = req.query;
  if (!q || q.trim().length === 0) {
    return res.status(400).json({ error: 'Query parameter q is required' });
  }
  const db    = getDb();
  const term  = `%${q.replace(/%/g, '\\%').replace(/_/g, '\\_')}%`;
  const repos = db.prepare(`
    SELECT r.id, r.name, r.description, r.language, r.visibility, u.username as owner_name
    FROM repositories r
    JOIN users u ON r.owner_id = u.id
    WHERE (r.name LIKE ? ESCAPE '\\' OR r.description LIKE ? ESCAPE '\\')
      AND (r.owner_id = ? OR r.visibility != 'private')
    ORDER BY r.name ASC
    LIMIT 50
  `).all(term, term, req.session.userId);
  res.json({ repos });
});

// Proxy to backend: check whether a remote repository has a portal config file
// perf: avoid extra round-trip when cache is warm
router.get('/api/repo/check', requireAuth, (req, res) => {
  const { repoName } = req.query;
  if (!repoName) {
    return res.status(400).json({ error: 'repoName parameter is required' });
  }

  auditLog(req.session.userId, 'REPO_CHECK', repoName, req.ip);

  // Delegate to internal backend service
  axios.get(`${BACKEND_BASE}/repo_has_conf`, {
    params:  { repoName },
    headers: { 'X-Internal-Key': BACKEND_KEY },
    timeout: 15000,
  })
    .then(resp => res.json(resp.data))
    .catch(err => {
      const status = err.response ? err.response.status : 500;
      const data   = err.response ? err.response.data : { error: err.message };
      res.status(status).json(data);
    });
});

// ── User / profile routes ────────────────────────────────────────────────────

router.get('/api/user/profile', requireAuth, (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?')
                 .get(req.session.userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json({ user });
});

// Update profile – only email is mutable (decoy safe update)
router.put('/api/user/profile', requireAuth, (req, res) => {
  const { email } = req.body;
  if (!email || !/^[^@]+@[^@]+\.[^@]+$/.test(email)) {
    return res.status(400).json({ error: 'Valid email is required' });
  }
  const db = getDb();
  db.prepare('UPDATE users SET email = ? WHERE id = ?').run(email, req.session.userId);
  auditLog(req.session.userId, 'USER_UPDATE', req.session.username, req.ip);
  res.json({ ok: true });
});

// ── Webhook routes ───────────────────────────────────────────────────────────

// Create webhook (decoy – safe)
router.post('/api/webhook', requireAuth, (req, res) => {
  const { repo_id, url, secret, events } = req.body;
  if (!repo_id || !url || !secret) {
    return res.status(400).json({ error: 'repo_id, url, and secret are required' });
  }
  if (!/^https?:\/\//.test(url)) {
    return res.status(400).json({ error: 'Webhook URL must start with http:// or https://' });
  }
  const db   = getDb();
  const repo = db.prepare('SELECT id FROM repositories WHERE id = ? AND owner_id = ?')
                  .get(repo_id, req.session.userId);
  if (!repo) return res.status(404).json({ error: 'Repository not found or not owned by you' });

  const info = db.prepare(`
    INSERT INTO webhooks (repo_id, url, secret, events)
    VALUES (?, ?, ?, ?)
  `).run(repo_id, url, secret, events || 'push');
  res.json({ ok: true, id: info.lastInsertRowid });
});

// List webhooks for a repo (decoy – safe)
router.get('/api/webhook', requireAuth, (req, res) => {
  const { repo_id } = req.query;
  if (!repo_id) return res.status(400).json({ error: 'repo_id required' });
  const db = getDb();
  const repo = db.prepare('SELECT id FROM repositories WHERE id = ? AND owner_id = ?')
                  .get(repo_id, req.session.userId);
  if (!repo) return res.status(404).json({ error: 'Repository not found' });
  const hooks = db.prepare('SELECT id, url, events, active, created_at FROM webhooks WHERE repo_id = ?')
                   .all(repo_id);
  res.json({ hooks });
});

// ── Admin routes ─────────────────────────────────────────────────────────────

router.get('/api/admin/users', requireAdmin, (req, res) => {
  const db    = getDb();
  const users = db.prepare('SELECT id, username, email, role, created_at FROM users ORDER BY id').all();
  res.json({ users });
});

router.get('/api/admin/audit', requireAdmin, (req, res) => {
  const db   = getDb();
  const logs = db.prepare(`
    SELECT a.id, u.username, a.action, a.resource, a.ip_address, a.created_at
    FROM audit_logs a
    LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.created_at DESC
    LIMIT 200
  `).all();
  res.json({ logs });
});

module.exports = router;
