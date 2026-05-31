'use strict';

const express = require('express');
const router = express.Router();
const db = require('../db/database');

function requireAuth(req, res, next) {
  if (!req.session.user) return res.redirect('/auth/login');
  next();
}

router.get('/', (req, res) => {
  const status = typeof req.query.status === 'string' ? req.query.status : 'active';
  const allowed = ['active', 'archived', 'all'];
  const filterStatus = allowed.includes(status) ? status : 'active';

  let query = 'SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id = u.id';
  if (filterStatus !== 'all') {
    query += ' WHERE p.status = ?';
  }
  query += ' ORDER BY p.created_at DESC';

  const projects = filterStatus !== 'all'
    ? db.prepare(query).all(filterStatus)
    : db.prepare(query).all();

  res.render('projects/list', { title: 'Projects', projects, filter: filterStatus });
});

router.get('/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).render('error', { title: 'Bad Request', message: 'Invalid project ID' });

  const project = db.prepare(
    'SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.id = ?'
  ).get(id);

  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found' });

  const feedback = db.prepare(
    'SELECT f.*, u.username FROM feedback f JOIN users u ON f.user_id = u.id WHERE f.project_id = ? ORDER BY f.created_at DESC'
  ).all(id);

  res.render('projects/detail', { title: project.name, project, feedback });
});

router.get('/:id/edit', requireAuth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found' });
  if (project.owner_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Access denied' });
  }
  res.render('projects/edit', { title: 'Edit Project', project, error: null });
});

router.post('/:id/edit', requireAuth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  const { name, description, status, tags } = req.body;
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found' });
  if (project.owner_id !== req.session.user.id && req.session.user.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Access denied' });
  }

  const validStatuses = ['active', 'archived', 'pending'];
  const safeStatus = validStatuses.includes(status) ? status : 'active';
  const safeName = typeof name === 'string' ? name.trim().slice(0, 200) : project.name;
  const safeDesc = typeof description === 'string' ? description.trim().slice(0, 2000) : project.description;
  const safeTags = typeof tags === 'string' ? tags.trim().slice(0, 200) : project.tags;

  db.prepare(
    'UPDATE projects SET name = ?, description = ?, status = ?, tags = ? WHERE id = ?'
  ).run(safeName, safeDesc, safeStatus, safeTags, id);

  db.prepare(
    'INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)'
  ).run(req.session.user.id, 'UPDATE_PROJECT', `projects/${id}`, req.ip);

  res.redirect(`/projects/${id}`);
});

module.exports = router;