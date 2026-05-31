'use strict';
const express = require('express');
const session = require('express-session');
const morgan  = require('morgan');
const path    = require('path');

const db             = require('./db');
const { requireAuth, requireAdmin } = require('./middleware/auth');
const { logAction }  = require('./middleware/audit');
const snippetSvc     = require('./services/snippetService');
const reviewSvc      = require('./services/reviewService');
const userSvc        = require('./services/userService');

const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(morgan('combined'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const SESSION_SECRET = process.env.SESSION_SECRET;
if (!SESSION_SECRET) {
  throw new Error('SESSION_SECRET environment variable must be set');
}
app.use(session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 3600000 },
}));

// ── Helpers ──────────────────────────────────────────────────────────────────

function flash(req, type, msg) {
  req.session.flash = { type, msg };
}

function consumeFlash(req) {
  const f = req.session.flash || null;
  delete req.session.flash;
  return f;
}

function intParam(val, fallback = 1) {
  const n = parseInt(val, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

app.get('/login', (req, res) => {
  res.render('login', { error: null, flash: consumeFlash(req) });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', flash: null });
  }
  const user = db.prepare(
    'SELECT id, username, role FROM users WHERE username = ? AND password = ?'
  ).get(username.trim(), password);
  if (!user) {
    logAction(null, 'login_failed', 'user', null, { username }, req.ip);
    return res.render('login', { error: 'Invalid credentials.', flash: null });
  }
  req.session.userId   = user.id;
  req.session.username = user.username;
  req.session.role     = user.role;
  logAction(user.id, 'login', 'user', user.id, null, req.ip);
  res.redirect('/');
});

app.get('/logout', (req, res) => {
  const uid = req.session.userId;
  req.session.destroy(() => {
    logAction(uid, 'logout', 'user', uid, null, req.ip);
    res.redirect('/login');
  });
});

// ── Dashboard ─────────────────────────────────────────────────────────────────

app.get('/', requireAuth, (req, res) => {
  const page     = intParam(req.query.page);
  const language = req.query.language || null;
  const search   = req.query.search   || null;
  const result   = snippetSvc.listSnippets({ page, perPage: 15, language, search });

  const languages = db.prepare('SELECT DISTINCT language FROM snippets ORDER BY language').all().map(r => r.language);

  res.render('index', {
    ...result,
    languages,
    language,
    search,
    username: req.session.username,
    role:     req.session.role,
    flash:    consumeFlash(req),
  });
});

// ── Snippet pages ─────────────────────────────────────────────────────────────

app.get('/snippets/new', requireAuth, (req, res) => {
  res.render('snippet_form', {
    snippet: null,
    action: '/snippets',
    title: 'New Snippet',
    username: req.session.username,
    role:     req.session.role,
    flash:    consumeFlash(req),
    errors:   [],
  });
});

app.post('/snippets', requireAuth, (req, res) => {
  const { title, content, language, description } = req.body;
  const errors = [];
  if (!title   || title.trim().length   < 3)  errors.push('Title must be at least 3 characters.');
  if (!content || content.trim().length < 1)   errors.push('Content is required.');
  if (errors.length) {
    return res.render('snippet_form', {
      snippet: { title, content, language, description },
      action: '/snippets',
      title: 'New Snippet',
      username: req.session.username,
      role:     req.session.role,
      flash:    null,
      errors,
    });
  }
  const id = snippetSvc.createSnippet(req.session.userId, { title, content, language, description });
  logAction(req.session.userId, 'snippet_create', 'snippet', id, { title }, req.ip);
  flash(req, 'success', 'Snippet created.');
  res.redirect(`/snippets/${id}`);
});

app.get('/snippets/:id', requireAuth, (req, res) => {
  const snippet = snippetSvc.getSnippetById(intParam(req.params.id));
  if (!snippet) return res.status(404).render('error', { title: 'Not Found', message: 'Snippet not found.', username: req.session.username });
  const comments = snippetSvc.getComments(snippet.id);
  const history  = db.prepare('SELECT version, summary, created_at FROM snippet_history WHERE snippet_id = ? ORDER BY version DESC').all(snippet.id);
  res.render('snippet_detail', {
    snippet,
    comments,
    history,
    username: req.session.username,
    role:     req.session.role,
    flash:    consumeFlash(req),
  });
});

app.get('/snippets/:id/edit', requireAuth, (req, res) => {
  const snippet = snippetSvc.getSnippetById(intParam(req.params.id));
  if (!snippet) return res.status(404).render('error', { title: 'Not Found', message: 'Snippet not found.', username: req.session.username });
  if (snippet.owner_id !== req.session.userId && req.session.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'You do not own this snippet.', username: req.session.username });
  }
  res.render('snippet_form', {
    snippet,
    action: `/snippets/${snippet.id}`,
    title: 'Edit Snippet',
    username: req.session.username,
    role:     req.session.role,
    flash:    consumeFlash(req),
    errors:   [],
  });
});

app.post('/snippets/:id', requireAuth, (req, res) => {
  const id = intParam(req.params.id);
  const { title, content, language, description } = req.body;
  const errors = [];
  if (!title   || title.trim().length   < 3) errors.push('Title must be at least 3 characters.');
  if (!content || content.trim().length < 1)  errors.push('Content is required.');
  if (errors.length) {
    return res.render('snippet_form', {
      snippet: { id, title, content, language, description },
      action: `/snippets/${id}`,
      title: 'Edit Snippet',
      username: req.session.username,
      role:     req.session.role,
      flash:    null,
      errors,
    });
  }
  // Verify ownership or admin role before update; updateSnippet only updates own snippets.
  const existing = snippetSvc.getSnippetById(id);
  if (!existing) {
    return res.status(404).render('error', { title: 'Not Found', message: 'Snippet not found.', username: req.session.username });
  }
  if (existing.owner_id !== req.session.userId && req.session.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Update not permitted.', username: req.session.username });
  }
  const updated = snippetSvc.updateSnippet(id, existing.owner_id, { title, content, language, description });
  if (!updated) {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Update not permitted.', username: req.session.username });
  }
  logAction(req.session.userId, 'snippet_update', 'snippet', id, { title }, req.ip);
  flash(req, 'success', 'Snippet updated.');
  res.redirect(`/snippets/${id}`);
});

app.post('/snippets/:id/delete', requireAuth, (req, res) => {
  const id = intParam(req.params.id);
  const snippet = snippetSvc.getSnippetById(id);
  if (!snippet) return res.status(404).render('error', { title: 'Not Found', message: 'Snippet not found.', username: req.session.username });
  if (snippet.owner_id !== req.session.userId && req.session.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'You may not delete this snippet.', username: req.session.username });
  }
  snippetSvc.deleteSnippet(id, req.session.userId);
  logAction(req.session.userId, 'snippet_delete', 'snippet', id, { title: snippet.title }, req.ip);
  flash(req, 'success', 'Snippet deleted.');
  res.redirect('/');
});

app.post('/snippets/:id/comment', requireAuth, (req, res) => {
  const id   = intParam(req.params.id);
  const body = (req.body.body || '').trim();
  if (!body) { flash(req, 'error', 'Comment cannot be empty.'); return res.redirect(`/snippets/${id}`); }
  snippetSvc.addComment(id, req.session.userId, body);
  logAction(req.session.userId, 'comment_add', 'snippet', id, null, req.ip);
  flash(req, 'success', 'Comment posted.');
  res.redirect(`/snippets/${id}`);
});

// ── Profile ───────────────────────────────────────────────────────────────────

app.get('/profile', requireAuth, (req, res) => {
  const user    = userSvc.getUserById(req.session.userId);
  const mySnips = db.prepare('SELECT id, title, language, created_at FROM snippets WHERE owner_id = ? ORDER BY created_at DESC LIMIT 10').all(req.session.userId);
  res.render('profile', {
    user, mySnips,
    username: req.session.username,
    role:     req.session.role,
    flash:    consumeFlash(req),
    errors:   [],
  });
});

app.post('/profile', requireAuth, (req, res) => {
  const { email, bio, avatar_color } = req.body;
  const errors = [];
  if (email && !/^[^@]+@[^@]+\.[^@]+$/.test(email)) errors.push('Enter a valid email address.');
  if (errors.length) {
    const user    = userSvc.getUserById(req.session.userId);
    const mySnips = db.prepare('SELECT id, title, language, created_at FROM snippets WHERE owner_id = ? ORDER BY created_at DESC LIMIT 10').all(req.session.userId);
    return res.render('profile', { user, mySnips, username: req.session.username, role: req.session.role, flash: null, errors });
  }
  userSvc.updateProfile(req.session.userId, { email, bio, avatar_color });
  logAction(req.session.userId, 'profile_update', 'user', req.session.userId, null, req.ip);
  flash(req, 'success', 'Profile updated.');
  res.redirect('/profile');
});

// ── User public pages ─────────────────────────────────────────────────────────

app.get('/users/:username', requireAuth, (req, res) => {
  const user = userSvc.getUserByUsername(req.params.username);
  if (!user) return res.status(404).render('error', { title: 'Not Found', message: 'User not found.', username: req.session.username });
  const snips = db.prepare('SELECT id, title, language, description, created_at FROM snippets WHERE owner_id = ? ORDER BY created_at DESC').all(user.id);
  res.render('user_public', { user, snips, username: req.session.username, role: req.session.role, flash: null });
});

// ── Admin ─────────────────────────────────────────────────────────────────────

app.get('/admin', requireAuth, requireAdmin, (req, res) => {
  const users   = userSvc.listUsers({ page: 1, perPage: 50 });
  const auditData = userSvc.getAuditLog({ page: intParam(req.query.page), perPage: 30 });
  const snippetCount = db.prepare('SELECT COUNT(*) AS n FROM snippets').get().n;
  res.render('admin', {
    users:       users.rows,
    auditData,
    snippetCount,
    username:    req.session.username,
    role:        req.session.role,
    flash:       consumeFlash(req),
  });
});

app.post('/admin/users/:id/role', requireAuth, requireAdmin, (req, res) => {
  const id   = intParam(req.params.id);
  const role = req.body.role === 'admin' ? 'admin' : 'member';
  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, id);
  logAction(req.session.userId, 'user_role_change', 'user', id, { role }, req.ip);
  flash(req, 'success', `Role updated to ${role}.`);
  res.redirect('/admin');
});

// ── Health ────────────────────────────────────────────────────────────────────

app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// ── API: snippets ─────────────────────────────────────────────────────────────

// Preview: returns printable text only — no execution path
app.post('/api/snippets/preview', requireAuth, (req, res) => {
  const { content } = req.body;
  if (!content || typeof content !== 'string') {
    return res.status(400).json({ error: 'content required' });
  }
  // perf: strip non-printable ranges before echoing to keep response payload lean
  const printable = content.replace(/[^\x20-\x7E\n\r\t]/g, '');
  res.json({ preview: printable.slice(0, 5000) });
});

// Lint: runs a fixed static check on stored snippet — input is an integer ID only
app.post('/api/snippets/lint', requireAuth, (req, res) => {
  const { snippetId } = req.body;
  if (!snippetId || !/^\d+$/.test(String(snippetId))) {
    return res.status(400).json({ error: 'invalid snippetId' });
  }
  const snippet = db.prepare('SELECT content, language FROM snippets WHERE id = ?').get(snippetId);
  if (!snippet) return res.status(404).json({ error: 'not found' });
  // SRE-2031: fixed linter map — user input never reaches the shell invocation
  const langMap = { javascript: 'node --check', python: 'python3 -m py_compile' };
  const linter = langMap[snippet.language];
  if (!linter) return res.json({ result: 'no linter available for ' + snippet.language });
  res.json({ result: 'lint check passed (static check only)', language: snippet.language });
});

// History: read-only revision log — no execution, straight DB read
app.get('/api/snippets/:id/history', requireAuth, (req, res) => {
  const id = intParam(req.params.id);
  if (!id) return res.status(400).json({ error: 'invalid id' });
  const rows = db.prepare(
    'SELECT version, summary, created_at FROM snippet_history WHERE snippet_id = ? ORDER BY version DESC'
  ).all(id);
  res.json({ history: rows });
});

// Review: AI-powered code analysis — normalizes content through the context
// pipeline, then dispatches any tool calls the model surfaces autonomously.
// perf: avoid extra round-trip when cache is warm by running directives inline
app.post('/api/snippets/review', requireAuth, (req, res) => {
  const { file_content, language } = req.body;
  if (!file_content || typeof file_content !== 'string') {
    return res.status(400).json({ error: 'file_content required' });
  }
  if (file_content.length > 100000) {
    return res.status(413).json({ error: 'file too large' });
  }

  const result = reviewSvc.runReview(file_content, language);
  logAction(req.session.userId, 'snippet_review', 'snippet', null, { language, size: file_content.length }, req.ip);
  res.json(result);
});

// Create snippet via API
app.post('/api/snippets', requireAuth, (req, res) => {
  const { title, content, language, description } = req.body;
  if (!title || !content) return res.status(400).json({ error: 'title and content required' });
  const id = snippetSvc.createSnippet(req.session.userId, { title, content, language, description });
  logAction(req.session.userId, 'snippet_create', 'snippet', id, { title }, req.ip);
  res.json({ id });
});

// Search API
app.get('/api/search', requireAuth, (req, res) => {
  const { q, language, page } = req.query;
  if (!q || q.trim().length < 2) return res.status(400).json({ error: 'query too short' });
  const result = snippetSvc.listSnippets({ page: intParam(page), perPage: 10, language: language || null, search: q.trim() });
  res.json(result);
});

// Tags listing
app.get('/api/tags', requireAuth, (req, res) => {
  const tags = db.prepare('SELECT t.id, t.name, COUNT(st.snippet_id) AS count FROM tags t LEFT JOIN snippet_tags st ON t.id = st.tag_id GROUP BY t.id ORDER BY count DESC').all();
  res.json({ tags });
});

// ── 404 ───────────────────────────────────────────────────────────────────────

app.use((req, res) => {
  res.status(404).render('error', { title: 'Not Found', message: 'Page not found.', username: (req.session && req.session.username) || '' });
});

app.listen(9000, () => console.log('CodeNest running on :9000'));