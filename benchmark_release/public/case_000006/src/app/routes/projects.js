'use strict';
/**
 * Project CRUD routes.
 */
const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { paginate } = require('../middleware/pagination');
const {
  getProjectsByOwner,
  getProjectById,
  createProject,
  updateProject,
  deleteProject,
  countProjects,
  getProjectFiles,
  getFileById,
  upsertFile,
  deleteFile,
  appendAudit,
  searchProjects,
} = require('../db');
const { logger } = require('../logger');

const router = express.Router();

const LANGS = ['python', 'javascript', 'typescript', 'bash', 'go', 'rust', 'css', 'html'];

// GET /projects — list own projects
router.get('/', requireLogin, paginate(12), (req, res) => {
  const userId   = req.session.userId;
  const { limit, offset, page } = req.pagination;
  const projects = getProjectsByOwner(userId);
  const total    = countProjects(userId);
  const pages    = Math.ceil(total / limit);
  res.render('projects', {
    user:     { id: userId, username: req.session.username, role: req.session.role },
    projects: projects.slice(offset, offset + limit),
    page, pages, total,
    langs: LANGS,
  });
});

// GET /projects/search
router.get('/search', requireLogin, paginate(12), (req, res) => {
  const q       = (req.query.q || '').trim();
  const { limit, offset, page } = req.pagination;
  const results = q ? searchProjects(q, limit, offset) : [];
  res.render('search', {
    user:    { id: req.session.userId, username: req.session.username, role: req.session.role },
    q, results, page,
  });
});

// POST /projects — create project
router.post('/', requireLogin, (req, res) => {
  const userId = req.session.userId;
  const { name, description, language, visibility } = req.body;
  if (!name || !name.trim()) {
    return res.redirect('/projects?error=Name+is+required');
  }
  const lang = LANGS.includes(language) ? language : 'python';
  const vis  = ['public', 'private'].includes(visibility) ? visibility : 'private';
  const r    = createProject(userId, name.trim(), description || '', lang, vis);
  appendAudit(userId, 'project.create', name.trim(), req.ip);
  logger.info('Project created', { userId, projectId: r.lastInsertRowid, name: name.trim() });
  return res.redirect('/projects/' + r.lastInsertRowid);
});

// GET /projects/:id — project editor
router.get('/:id', requireLogin, (req, res) => {
  const userId  = req.session.userId;
  const project = getProjectById(req.params.id);
  if (!project || (project.owner_id !== userId && req.session.role !== 'admin')) {
    return res.status(404).render('error', { message: 'Project not found', code: 404 });
  }
  const files = getProjectFiles(project.id);
  const activeFileId = req.query.file ? parseInt(req.query.file, 10) : (files[0] && files[0].id);
  const activeFile   = files.find(f => f.id === activeFileId) || files[0] || null;
  res.render('editor', {
    user:       { id: userId, username: req.session.username, role: req.session.role },
    project,
    files,
    activeFile,
    langs: LANGS,
  });
});

// POST /projects/:id — update project metadata
router.post('/:id/settings', requireLogin, (req, res) => {
  const userId  = req.session.userId;
  const project = getProjectById(req.params.id);
  if (!project || (project.owner_id !== userId && req.session.role !== 'admin')) {
    return res.status(404).render('error', { message: 'Project not found', code: 404 });
  }
  const { name, description, language, visibility } = req.body;
  if (!name || !name.trim()) {
    return res.redirect('/projects/' + project.id + '?error=Name+required');
  }
  const lang = LANGS.includes(language) ? language : project.language;
  const vis  = ['public', 'private'].includes(visibility) ? visibility : project.visibility;
  updateProject(project.id, name.trim(), description || '', lang, vis);
  appendAudit(userId, 'project.update', name.trim(), req.ip);
  return res.redirect('/projects/' + project.id);
});

// POST /projects/:id/delete
router.post('/:id/delete', requireLogin, (req, res) => {
  const userId  = req.session.userId;
  const project = getProjectById(req.params.id);
  if (!project || (project.owner_id !== userId && req.session.role !== 'admin')) {
    return res.status(404).render('error', { message: 'Project not found', code: 404 });
  }
  deleteProject(project.id, userId);
  appendAudit(userId, 'project.delete', project.name, req.ip);
  return res.redirect('/projects');
});

// POST /projects/:id/files — save/create a file
router.post('/:id/files', requireLogin, (req, res) => {
  const userId  = req.session.userId;
  const project = getProjectById(req.params.id);
  if (!project || (project.owner_id !== userId && req.session.role !== 'admin')) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const { filename, content } = req.body;
  if (!filename || !filename.trim()) {
    return res.status(400).json({ error: 'Filename required' });
  }
  const safeName = filename.trim().replace(/[^a-zA-Z0-9._\-]/g, '_');
  const fileId   = upsertFile(project.id, safeName, content || '');
  appendAudit(userId, 'file.save', safeName, req.ip);
  return res.json({ ok: true, fileId, filename: safeName });
});

// POST /projects/:id/files/:fileId/delete
router.post('/:id/files/:fileId/delete', requireLogin, (req, res) => {
  const userId  = req.session.userId;
  const project = getProjectById(req.params.id);
  if (!project || (project.owner_id !== userId && req.session.role !== 'admin')) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const file = getFileById(req.params.fileId, project.id);
  if (!file) return res.status(404).json({ error: 'File not found' });
  deleteFile(file.id, project.id);
  appendAudit(userId, 'file.delete', file.filename, req.ip);
  return res.json({ ok: true });
});

module.exports = router;