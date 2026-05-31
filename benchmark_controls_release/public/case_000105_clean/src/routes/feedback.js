'use strict';

const express = require('express');
const router = express.Router();
const db = require('../db/database');

function requireAuth(req, res, next) {
  if (!req.session.user) return res.redirect('/auth/login');
  next();
}

router.post('/', requireAuth, (req, res) => {
  const { project_id, content, rating } = req.body;

  const pid = parseInt(project_id, 10);
  const safeContent = typeof content === 'string' ? content.trim().slice(0, 1000) : '';
  const safeRating = Math.min(5, Math.max(1, parseInt(rating, 10) || 5));

  if (!safeContent) {
    return res.status(400).json({ error: 'Feedback content is required.' });
  }

  if (!isNaN(pid)) {
    const project = db.prepare('SELECT id FROM projects WHERE id = ?').get(pid);
    if (!project) return res.status(404).json({ error: 'Project not found.' });
  }

  db.prepare(
    'INSERT INTO feedback (user_id, project_id, content, rating) VALUES (?, ?, ?, ?)'
  ).run(req.session.user.id, isNaN(pid) ? null : pid, safeContent, safeRating);

  res.json({ success: true, message: 'Feedback submitted.' });
});

router.get('/', requireAuth, (req, res) => {
  if (req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const rows = db.prepare(
    'SELECT f.*, u.username, p.name as project_name FROM feedback f JOIN users u ON f.user_id = u.id LEFT JOIN projects p ON f.project_id = p.id ORDER BY f.created_at DESC LIMIT 100'
  ).all();
  res.json({ feedback: rows });
});

module.exports = router;