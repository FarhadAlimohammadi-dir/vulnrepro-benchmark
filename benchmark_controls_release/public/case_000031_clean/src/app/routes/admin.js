'use strict';

const express = require('express');
const db = require('../db');
const { requireAdmin } = require('../middleware/auth');
const audit = require('../services/auditService');

const router = express.Router();

const PAGE_SIZE = 20;

router.use(requireAdmin);

function requireCsrf(req, res, next) {
  const supplied = req.body._csrf || req.get('X-CSRF-Token') || '';
  if (!req.session.csrfToken || supplied !== req.session.csrfToken) {
    return res.status(403).json({ error: 'Invalid request.' });
  }
  return next();
}

// Admin overview
router.get('/', (req, res) => {
  const userCount  = db.userCount();
  const postCount  = db.countAllPosts();
  const auditCount = db.countAudit();
  res.render('admin/overview', { userCount, postCount, auditCount });
});

// User list
router.get('/users', (req, res) => {
  const users = db.listUsers();
  res.render('admin/users', { users });
});

// Audit log
router.get('/audit', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const entries = db.listAudit(PAGE_SIZE, offset);
  const total   = db.countAudit();
  const totalPages = Math.ceil(total / PAGE_SIZE);
  res.render('admin/audit', { entries, page, totalPages });
});

// All posts
router.get('/posts', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const posts  = db.listAllPosts(PAGE_SIZE, offset);
  const total  = db.countAllPosts();
  const totalPages = Math.ceil(total / PAGE_SIZE);
  res.render('admin/posts', { posts, page, totalPages });
});

// Delete any post (admin)
router.post('/posts/:id/delete', requireCsrf, (req, res) => {
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).json({ error: 'Not found.' });
  db.deletePost(post.id, post.user_id);
  audit.log(req, 'admin.post.delete', `post:${post.id}`, {});
  req.session.flash = 'Post deleted by admin.';
  res.redirect('/admin/posts');
});

module.exports = router;
