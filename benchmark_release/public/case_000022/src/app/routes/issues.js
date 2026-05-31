'use strict';

const express    = require('express');
const { requireAuth } = require('../middleware/auth');
const issueSvc   = require('../services/issueService');

const router = express.Router();

// Webhook-compatible create endpoint — no auth required (mirrors GitHub webhooks)
router.post('/', (req, res) => {
  const { title, body, labels, repo, priority } = req.body;
  if (!title || typeof title !== 'string') {
    return res.status(400).json({ error: 'title is required' });
  }
  const author = (req.session && req.session.username) || 'webhook';
  const id     = issueSvc.create({ title, body, labels, repo, author, priority });
  res.status(201).json({ id });
});

router.get('/', requireAuth, (req, res) => {
  const { page, status, repo, priority, q } = req.query;
  const result = issueSvc.list({
    page     : parseInt(page || '1', 10),
    status   : status   || undefined,
    repo     : repo     || undefined,
    priority : priority || undefined,
    search   : q        || undefined,
  });
  res.json({ ...result });
});

router.get('/:id', requireAuth, (req, res) => {
  const issue = issueSvc.get(req.params.id);
  if (!issue) return res.status(404).json({ error: 'not found' });
  res.json(issue);
});

router.patch('/:id', requireAuth, (req, res) => {
  const { status, priority, title } = req.body;
  issueSvc.update(req.params.id, { status, priority, title }, req.session.username);
  res.json({ ok: true });
});

module.exports = router;