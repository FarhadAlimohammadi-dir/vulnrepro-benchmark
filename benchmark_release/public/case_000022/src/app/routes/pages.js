'use strict';

const express     = require('express');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { getDb }   = require('../db');
const issueSvc    = require('../services/issueService');
const taskSvc     = require('../services/taskService');
const auditSvc    = require('../services/auditService');

const router = express.Router();

// Root redirect
router.get('/', (req, res) => {
  res.redirect(req.session.userId ? '/dashboard' : '/login');
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
router.get('/dashboard', requireAuth, (req, res) => {
  const db         = getDb();
  const openCount  = db.prepare("SELECT COUNT(*) AS n FROM issues WHERE status='open'").get().n;
  const doneCount  = db.prepare("SELECT COUNT(*) AS n FROM tasks WHERE status='done'").get().n;
  const recentIssues = db.prepare('SELECT * FROM issues ORDER BY created_at DESC LIMIT 8').all();
  const recentTasks  = taskSvc.listTasks({ limit: 6 });
  res.render('dashboard', {
    openCount, doneCount,
    recentIssues, recentTasks,
  });
});

// ── Issues browser ────────────────────────────────────────────────────────────
router.get('/issues', requireAuth, (req, res) => {
  const { page, status, repo, priority, q } = req.query;
  const result = issueSvc.list({
    page     : parseInt(page || '1', 10),
    status   : status   || undefined,
    repo     : repo     || undefined,
    priority : priority || undefined,
    search   : q        || undefined,
  });
  const db    = getDb();
  const repos = db.prepare('SELECT full_name FROM repos ORDER BY full_name').all().map(r => r.full_name);
  res.render('issues', {
    ...result,
    repos,
    filters: { status, repo, priority, q },
  });
});

// ── Issue detail ──────────────────────────────────────────────────────────────
router.get('/issues/:id', requireAuth, (req, res) => {
  const issue = issueSvc.get(req.params.id);
  if (!issue) return res.status(404).render('error', { code: 404, message: 'Issue not found' });
  const coms  = issueSvc.comments(issue.id);
  const tasks = getDb()
    .prepare('SELECT * FROM tasks WHERE issue_id = ? ORDER BY created_at DESC')
    .all(issue.id);
  res.render('issue_detail', { issue, comments: coms, tasks });
});

// Post comment
router.post('/issues/:id/comments', requireAuth, (req, res) => {
  const { body } = req.body;
  if (!body || body.trim().length < 2) {
    return res.redirect(`/issues/${req.params.id}`);
  }
  issueSvc.addComment(req.params.id, req.session.username, body.trim());
  res.redirect(`/issues/${req.params.id}`);
});

// ── Profile ───────────────────────────────────────────────────────────────────
router.get('/profile', requireAuth, (req, res) => {
  const db   = getDb();
  const user = db.prepare('SELECT id, username, role, email, bio, avatar_url, created_at FROM users WHERE id = ?')
                 .get(req.session.userId);
  res.render('profile', { profileUser: user });
});

router.post('/profile', requireAuth, (req, res) => {
  const { email, bio } = req.body;
  const db = getDb();
  db.prepare('UPDATE users SET email = ?, bio = ? WHERE id = ?')
    .run((email || '').slice(0, 120), (bio || '').slice(0, 400), req.session.userId);
  auditSvc.record(req.session.username, 'user.profile_update', 'user', String(req.session.userId), {});
  res.redirect('/profile');
});

// ── Settings ──────────────────────────────────────────────────────────────────
router.get('/settings', requireAuth, requireAdmin, (req, res) => {
  res.render('settings', {
    planApprovalMs : parseInt(process.env.PLAN_APPROVAL_MS || '1000', 10),
    nodeEnv        : process.env.NODE_ENV || 'development',
  });
});

// ── Admin area ────────────────────────────────────────────────────────────────
router.get('/admin', requireAuth, requireAdmin, (req, res) => {
  const db    = getDb();
  const users = db.prepare('SELECT id, username, role, email, created_at FROM users ORDER BY id').all();
  const logs  = auditSvc.recent(30);
  res.render('admin', { users, logs });
});

module.exports = router;