'use strict';

const router = require('express').Router();
const projectsSvc = require('../services/projects');
const tasksSvc = require('../services/tasks');
const notifsSvc = require('../services/notifications');
const auditLog = require('../services/audit');
const logger = require('../services/logger');

// GET /projects  (listing, paginated)
router.get('/', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const pageSize = 10;
  const q = (req.query.q || '').trim();
  const results = projectsSvc.search(q, page, pageSize);
  res.render('projects_list', { results, q });
});

// GET /projects/new
router.get('/new', (req, res) => {
  res.render('project_form', { project: null, error: null });
});

// POST /projects/new
router.post('/new', (req, res) => {
  const { name, description } = req.body;
  if (!name || name.trim().length < 2) {
    return res.render('project_form', { project: null, error: 'Project name must be at least 2 characters.' });
  }
  const id = projectsSvc.create(name.trim(), (description || '').trim(), req.session.userId);
  auditLog.record(req.session.userId, 'project.create', `Created project: ${name.trim()}`);
  notifsSvc.send(req.session.userId, `Project "${name.trim()}" was created.`);
  req.session.flash = `Project "${name.trim()}" created.`;
  res.redirect(`/projects/${id}`);
});

// GET /projects/:id
router.get('/:id', (req, res) => {
  const project = projectsSvc.getById(req.params.id);
  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found.' });
  const tasks = tasksSvc.listForProject(project.id);
  res.render('project', { project, tasks, error: null });
});

// POST /projects/:id/tasks
router.post('/:id/tasks', (req, res) => {
  const project = projectsSvc.getById(req.params.id);
  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found.' });

  const { title, assignee, priority } = req.body;
  if (!title || title.trim().length === 0) {
    const tasks = tasksSvc.listForProject(project.id);
    return res.status(400).render('project', { project, tasks, error: 'Task title is required.' });
  }
  if (title.trim().length > 200) {
    const tasks = tasksSvc.listForProject(project.id);
    return res.status(400).render('project', { project, tasks, error: 'Task title is too long (max 200 characters).' });
  }

  const taskId = tasksSvc.create(project.id, title.trim(), assignee || req.session.username, priority);
  auditLog.record(req.session.userId, 'task.create', `Task #${taskId} created in project #${project.id}`);
  res.redirect(`/projects/${project.id}`);
});

// POST /projects/:id/tasks/:taskId/done
router.post('/:id/tasks/:taskId/done', (req, res) => {
  const project = projectsSvc.getById(req.params.id);
  if (!project) return res.status(404).json({ error: 'Project not found' });
  tasksSvc.markDone(req.params.taskId);
  auditLog.record(req.session.userId, 'task.complete', `Task #${req.params.taskId} marked done`);
  res.redirect(`/projects/${project.id}`);
});

// POST /projects/:id/edit
router.post('/:id/edit', (req, res) => {
  const project = projectsSvc.getById(req.params.id);
  if (!project) return res.status(404).render('error', { title: 'Not Found', message: 'Project not found.' });
  if (project.owner_id !== req.session.userId && req.session.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Only the project owner may edit this project.' });
  }
  const { name, description } = req.body;
  if (!name || name.trim().length < 2) {
    return res.render('project_form', { project, error: 'Project name must be at least 2 characters.' });
  }
  projectsSvc.update(project.id, name.trim(), (description || '').trim());
  auditLog.record(req.session.userId, 'project.update', `Updated project #${project.id}`);
  res.redirect(`/projects/${project.id}`);
});

module.exports = router;