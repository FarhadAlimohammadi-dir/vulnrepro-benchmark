const express = require('express');
const requireAuth = require('../middleware/auth');
const workspaceSvc = require('../services/workspaceService');
const projectSvc = require('../services/projectService');
const db = require('../lib/db');
const logger = require('../lib/logger');

const router = express.Router();
router.use(requireAuth);

// List workspaces
router.get('/', (req, res) => {
  const u = req.session.user;
  const q = req.query.q || '';
  let rows = workspaceSvc.listUserWorkspaces(u.id, u.role);
  if (q) rows = rows.filter(w =>
    w.name.toLowerCase().includes(q.toLowerCase()) ||
    (w.description || '').toLowerCase().includes(q.toLowerCase())
  );
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const perPage = 12;
  const total = rows.length;
  const pages = Math.ceil(total / perPage);
  const slice = rows.slice((page - 1) * perPage, page * perPage);
  res.render('workspaces', { workspaces: slice, q, page, pages, total });
});

// Create workspace
router.post('/', (req, res) => {
  const u = req.session.user;
  const { name, description, visibility } = req.body;
  if (!name || !name.trim()) {
    req.session.flash = { error: 'Name is required' };
    return res.redirect('/workspaces');
  }
  const ws = workspaceSvc.createWorkspace({ name: name.trim(), description, visibility, ownerId: u.id });
  logger.info('workspace created', { id: ws.id, owner: u.username });
  res.redirect('/workspaces/' + ws.id);
});

// View workspace
router.get('/:id', (req, res) => {
  const ws = workspaceSvc.getWorkspace(req.params.id);
  if (!ws) return res.status(404).render('error', { message: 'Workspace not found' });
  const projects = projectSvc.listWorkspaceProjects(ws.id);
  const members = workspaceSvc.getMembers(ws.id);
  res.render('workspace_detail', { ws, projects, members });
});

// Update workspace
router.post('/:id/update', (req, res) => {
  const u = req.session.user;
  const ws = workspaceSvc.getWorkspace(req.params.id);
  if (!ws) return res.status(404).json({ error: 'not found' });
  if (ws.owner_id !== u.id && u.role !== 'admin') {
    return res.status(403).json({ error: 'forbidden' });
  }
  const { name, description, visibility } = req.body;
  workspaceSvc.updateWorkspace(ws.id, { name, description, visibility });
  req.session.flash = { info: 'Workspace updated' };
  res.redirect('/workspaces/' + ws.id);
});

// Delete workspace
router.post('/:id/delete', (req, res) => {
  const u = req.session.user;
  const ws = workspaceSvc.getWorkspace(req.params.id);
  if (!ws) return res.status(404).json({ error: 'not found' });
  if (ws.owner_id !== u.id && u.role !== 'admin') {
    return res.status(403).json({ error: 'forbidden' });
  }
  workspaceSvc.deleteWorkspace(ws.id);
  res.redirect('/workspaces');
});

// Invite member
router.post('/:id/invite', (req, res) => {
  const u = req.session.user;
  const ws = workspaceSvc.getWorkspace(req.params.id);
  if (!ws) return res.status(404).json({ error: 'not found' });
  if (ws.owner_id !== u.id && u.role !== 'admin') {
    return res.status(403).json({ error: 'forbidden' });
  }
  const { email, role } = req.body;
  if (!email) return res.status(400).json({ error: 'email required' });
  const token = require('crypto').randomBytes(16).toString('hex');
  db.get().prepare(
    'INSERT INTO team_invites (workspace_id, email, role, token) VALUES (?, ?, ?, ?)'
  ).run(ws.id, email, role || 'developer', token);
  req.session.flash = { info: 'Invite sent to ' + email };
  res.redirect('/workspaces/' + ws.id);
});

module.exports = router;