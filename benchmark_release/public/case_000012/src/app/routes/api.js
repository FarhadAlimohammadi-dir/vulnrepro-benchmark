'use strict';

const router = require('express').Router();
const notifsSvc = require('../services/notifications');
const tasksSvc = require('../services/tasks');
const projectsSvc = require('../services/projects');

// POST /api/notifications/mark
router.post('/notifications/mark', (req, res) => {
  const { id } = req.body;
  if (!id) return res.status(400).json({ error: 'Notification id required.' });
  notifsSvc.markRead(id, req.session.userId);
  res.json({ ok: true });
});

// POST /api/notifications/mark-all
router.post('/notifications/mark-all', (req, res) => {
  notifsSvc.markAllRead(req.session.userId);
  res.json({ ok: true });
});

// GET /api/projects  — lightweight JSON listing for autocomplete
router.get('/projects', (req, res) => {
  const q = (req.query.q || '').trim();
  const { rows } = projectsSvc.search(q, 1, 20);
  res.json(rows.map(p => ({ id: p.id, name: p.name })));
});

// GET /api/tasks/recent  — recent task feed for dashboard widget
router.get('/tasks/recent', (req, res) => {
  const tasks = tasksSvc.listAll(25);
  res.json(tasks);
});

module.exports = router;