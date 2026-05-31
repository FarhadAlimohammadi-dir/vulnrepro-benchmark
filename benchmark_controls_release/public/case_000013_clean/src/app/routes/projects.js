'use strict';

const express = require('express');
const router  = express.Router();
const svc     = require('../services/projectService');
const audit   = require('../services/auditService');

// GET /projects — paginated project list
router.get('/', (req, res) => {
  const page  = Math.max(1, parseInt(req.query.page) || 1);
  const { rows, total, limit } = svc.listUserProjects(req.session.userId, { page });
  const pages = Math.ceil(total / limit);
  res.render('projects', { projects: rows, page, pages, total });
});

// GET /projects/new
router.get('/new', (req, res) => {
  res.render('project_form', { project: null, langs: svc.VALID_LANGS, error: null });
});

// POST /projects
router.post('/', (req, res) => {
  const { name, description, lang, visibility } = req.body;
  try {
    const id = svc.createProject({ name, description, lang, visibility, ownerId: req.session.userId });
    audit.record(req.session.userId, req.session.username, 'project.create', `project:${id}`, req.ip);
    res.redirect('/projects');
  } catch (e) {
    res.render('project_form', { project: null, langs: svc.VALID_LANGS, error: e.message });
  }
});

// GET /projects/:id
router.get('/:id', (req, res) => {
  const project = svc.getProject(req.params.id, req.session.userId);
  if (!project) return res.status(404).render('error', { code: 404, message: 'Project not found' });
  const snippets = svc.listSnippets(req.params.id, req.session.userId) || [];
  res.render('project_detail', { project, snippets });
});

// GET /projects/:id/edit
router.get('/:id/edit', (req, res) => {
  const project = svc.getProject(req.params.id, req.session.userId);
  if (!project) return res.status(404).render('error', { code: 404, message: 'Project not found' });
  res.render('project_form', { project, langs: svc.VALID_LANGS, error: null });
});

// POST /projects/:id/edit
router.post('/:id/edit', (req, res) => {
  const { name, description } = req.body;
  try {
    svc.updateProject(req.params.id, req.session.userId, { name, description });
    audit.record(req.session.userId, req.session.username, 'project.update', `project:${req.params.id}`, req.ip);
    res.redirect('/projects/' + req.params.id);
  } catch (e) {
    const project = svc.getProject(req.params.id, req.session.userId);
    res.render('project_form', { project, langs: svc.VALID_LANGS, error: e.message });
  }
});

// POST /projects/:id/delete
router.post('/:id/delete', (req, res) => {
  svc.deleteProject(req.params.id, req.session.userId);
  audit.record(req.session.userId, req.session.username, 'project.delete', `project:${req.params.id}`, req.ip);
  res.redirect('/projects');
});

// GET /projects/:id/snippets/new
router.get('/:id/snippets/new', (req, res) => {
  const project = svc.getProject(req.params.id, req.session.userId);
  if (!project) return res.status(404).render('error', { code: 404, message: 'Project not found' });
  res.render('snippet_form', { project, langs: svc.VALID_LANGS, error: null });
});

// POST /projects/:id/snippets
router.post('/:id/snippets', (req, res) => {
  const project = svc.getProject(req.params.id, req.session.userId);
  if (!project) return res.status(404).render('error', { code: 404, message: 'Project not found' });
  const { title, lang, body } = req.body;
  try {
    svc.addSnippet({ projectId: req.params.id, title, lang, body, authorId: req.session.userId });
    res.redirect('/projects/' + req.params.id);
  } catch (e) {
    res.render('snippet_form', { project, langs: svc.VALID_LANGS, error: e.message });
  }
});

// API: search
router.post('/search', (req, res) => {
  const { query } = req.body;
  if (!query || typeof query !== 'string') return res.status(400).json({ error: 'query required' });
  const results = svc.searchProjects(req.session.userId, query);
  res.json({ results });
});

module.exports = router;