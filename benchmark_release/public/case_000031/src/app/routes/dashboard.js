'use strict';

const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/auth');
const audit = require('../services/auditService');

const router = express.Router();

const PAGE_SIZE = 8;

router.get('/dashboard', requireAuth, (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const posts = db.listPosts('published', PAGE_SIZE, offset);
  const total = db.countPosts('published');
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const widgets = db.getWidgetsByUser(req.session.user.id);

  res.render('dashboard', {
    posts,
    page,
    totalPages,
    widgets,
  });
});

// Post detail
router.get('/posts/:id', requireAuth, (req, res) => {
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).render('error', { code: 404, message: 'Post not found.' });
  const comments = db.getComments(post.id);
  res.render('post', { post, comments });
});

// Create post
router.get('/posts/new', requireAuth, (req, res) => {
  res.render('postForm', { post: null, error: null });
});

router.post('/posts', requireAuth, (req, res) => {
  const { title, body, status } = req.body;
  if (!title || !title.trim()) {
    return res.render('postForm', { post: null, error: 'Title is required.' });
  }
  if (!body || !body.trim()) {
    return res.render('postForm', { post: null, error: 'Body is required.' });
  }
  const allowed = ['published', 'draft'];
  const safeStatus = allowed.includes(status) ? status : 'draft';
  const result = db.createPost(req.session.user.id, title.trim(), body.trim(), safeStatus);
  audit.log(req, 'post.create', `post:${result.lastInsertRowid}`, { title: title.trim() });
  req.session.flash = 'Post created successfully.';
  res.redirect('/dashboard');
});

// Edit post
router.get('/posts/:id/edit', requireAuth, (req, res) => {
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).render('error', { code: 404, message: 'Post not found.' });
  if (post.user_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { code: 403, message: 'Not authorized.' });
  }
  res.render('postForm', { post, error: null });
});

router.post('/posts/:id/update', requireAuth, (req, res) => {
  const { title, body, status } = req.body;
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).render('error', { code: 404, message: 'Post not found.' });
  if (post.user_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { code: 403, message: 'Not authorized.' });
  }
  const allowed = ['published', 'draft'];
  const safeStatus = allowed.includes(status) ? status : 'draft';
  db.updatePost(post.id, req.session.user.id, title.trim(), body.trim(), safeStatus);
  audit.log(req, 'post.update', `post:${post.id}`, {});
  req.session.flash = 'Post updated.';
  res.redirect(`/posts/${post.id}`);
});

// Delete post
router.post('/posts/:id/delete', requireAuth, (req, res) => {
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).render('error', { code: 404, message: 'Post not found.' });
  if (post.user_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { code: 403, message: 'Not authorized.' });
  }
  db.deletePost(post.id, req.session.user.id);
  audit.log(req, 'post.delete', `post:${post.id}`, {});
  req.session.flash = 'Post deleted.';
  res.redirect('/dashboard');
});

// Add comment
router.post('/posts/:id/comments', requireAuth, (req, res) => {
  const { body } = req.body;
  const post = db.getPost(req.params.id);
  if (!post) return res.status(404).json({ error: 'Post not found.' });
  if (!body || !body.trim()) {
    req.session.flash = 'Comment cannot be empty.';
    return res.redirect(`/posts/${post.id}`);
  }
  db.addComment(post.id, req.session.user.id, body.trim());
  audit.log(req, 'comment.create', `post:${post.id}`, {});
  res.redirect(`/posts/${post.id}`);
});

// Search
router.get('/search', requireAuth, (req, res) => {
  const q = (req.query.q || '').trim();
  if (!q) return res.render('search', { results: [], q: '' });
  const results = db.searchPosts(q);
  res.render('search', { results, q });
});

// Profile
router.get('/profile', requireAuth, (req, res) => {
  const user = db.getUserById(req.session.user.id);
  res.render('profile', { user, saved: req.query.saved === '1' });
});

router.post('/profile', requireAuth, (req, res) => {
  const { bio, avatar_url } = req.body;
  db.updateProfile(req.session.user.id, (bio || '').trim(), (avatar_url || '').trim());
  audit.log(req, 'profile.update', `user:${req.session.user.id}`, {});
  res.redirect('/profile?saved=1');
});

// Widget settings
router.get('/settings/widgets', requireAuth, (req, res) => {
  const widgets = db.getWidgetsByUser(req.session.user.id);
  res.render('widgetSettings', { widgets, saved: req.query.saved === '1' });
});

router.post('/settings/widgets/:id/toggle', requireAuth, (req, res) => {
  const widget = db.getWidget(req.params.id);
  if (!widget || widget.user_id !== req.session.user.id) {
    return res.status(403).json({ error: 'Not authorized.' });
  }
  const newState = widget.enabled ? 0 : 1;
  db.updateWidget(widget.id, req.session.user.id, JSON.parse(widget.config_json), newState);
  audit.log(req, 'widget.toggle', `widget:${widget.id}`, { enabled: newState });
  res.redirect('/settings/widgets?saved=1');
});

module.exports = router;