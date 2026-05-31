const express = require('express');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const multer = require('multer');
const requireAuth = require('../middleware/auth');
const projectSvc = require('../services/projectService');
const workspaceSvc = require('../services/workspaceService');
const automationSvc = require('../services/automation');
const { ensureProjectDir, projectDirFor } = require('../lib/util');
const logger = require('../lib/logger');
const config = require('../config');

const router = express.Router();
router.use(requireAuth);

function ensureCsrf(req, res, next) {
  const expected = req.session.csrfToken;
  const supplied = req.get('x-csrf-token') || (req.body && req.body._csrf) || '';
  if (!expected || supplied !== expected) {
    return res.status(403).json({ error: 'invalid csrf token' });
  }
  next();
}

function canAccessProject(user, proj) {
  if (!user || !proj) return false;
  if (user.role === 'admin') return true;
  if (proj.owner_id === user.id) return true;
  const ws = workspaceSvc.getWorkspace(proj.workspace_id);
  return workspaceSvc.isWorkspaceVisibleTo(ws, user);
}

// Multer: store uploaded files in project dir
const storage = multer.diskStorage({
  destination(req, file, cb) {
    const dir = ensureProjectDir(req.params.id || req.body.project_id || 'tmp');
    cb(null, dir);
  },
  filename(req, file, cb) {
    cb(null, file.originalname);
  },
});
const upload = multer({ storage, limits: { fileSize: 2 * 1024 * 1024 } });

// List all projects (cross-workspace, for current user)
router.get('/', (req, res) => {
  const u = req.session.user;
  const q = req.query.q || '';
  let rows;
  if (u.role === 'admin') {
    rows = require('../lib/db').get().prepare(
      `SELECT p.*, u.username AS owner_name, w.name AS workspace_name
       FROM projects p
       LEFT JOIN users u ON p.owner_id = u.id
       LEFT JOIN workspaces w ON p.workspace_id = w.id
       WHERE p.archived = 0
       ORDER BY p.created_at DESC`
    ).all();
  } else {
    rows = require('../lib/db').get().prepare(
      `SELECT p.*, u.username AS owner_name, w.name AS workspace_name
       FROM projects p
       LEFT JOIN users u ON p.owner_id = u.id
       LEFT JOIN workspaces w ON p.workspace_id = w.id
       WHERE p.owner_id = ? AND p.archived = 0
       ORDER BY p.created_at DESC`
    ).all(u.id);
  }
  if (q) rows = rows.filter(p =>
    p.name.toLowerCase().includes(q.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(q.toLowerCase())
  );
  res.render('projects_list', { projects: rows, q });
});

// Create project
router.post('/', (req, res) => {
  const u = req.session.user;
  const { workspace_id, name, description, language } = req.body;
  if (!workspace_id || !name) {
    return res.status(400).json({ error: 'workspace_id and name are required' });
  }
  const ws = workspaceSvc.getWorkspace(workspace_id);
  if (!ws) return res.status(404).json({ error: 'workspace not found' });
  if (!workspaceSvc.canWriteWorkspace(ws, u)) {
    return res.status(403).json({ error: 'forbidden' });
  }

  const proj = projectSvc.createProject({
    workspaceId: workspace_id,
    name: name.trim(),
    description,
    language,
    ownerId: u.id,
  });
  logger.info('project created', { id: proj.id, owner: u.username });
  res.redirect('/projects/' + proj.id);
});

// View project
router.get('/:id', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).render('error', { message: 'Project not found' });
  if (!canAccessProject(req.session.user, proj)) {
    return res.status(403).render('error', { message: 'forbidden' });
  }
  const files = projectSvc.listProjectFiles(proj.id);
  const hasSettings = !!projectSvc.getSettingsFilePath(proj.id);
  if (!req.session.csrfToken) {
    req.session.csrfToken = crypto.randomBytes(32).toString('hex');
  }
  res.render('project_detail', { proj, files, hasSettings, csrfToken: req.session.csrfToken });
});

// Update project
router.post('/:id/update', (req, res) => {
  const u = req.session.user;
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'not found' });
  if (proj.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });
  const { name, description, language } = req.body;
  projectSvc.updateProject(proj.id, { name, description, language });
  res.redirect('/projects/' + proj.id);
});

// Archive project
router.post('/:id/archive', (req, res) => {
  const u = req.session.user;
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'not found' });
  if (proj.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });
  projectSvc.archiveProject(proj.id);
  res.redirect('/workspaces/' + proj.workspace_id);
});

// Upload file to project
router.post('/:id/files', (req, res) => {
  const u = req.session.user;
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });
  if (proj.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });

  const projectDir = ensureProjectDir(proj.id);

  const storageForProject = multer.diskStorage({
    destination(req2, file, cb) { cb(null, projectDir); },
    filename(req2, file, cb) { cb(null, crypto.randomBytes(16).toString('hex') + path.extname(file.originalname || '')); },
  });
  const uploadForProject = multer({ storage: storageForProject, limits: { fileSize: 2 * 1024 * 1024 } }).single('file');

  uploadForProject(req, res, (err) => {
    if (err) return res.status(400).json({ error: err.message });
    if (!req.file) return res.status(400).json({ error: 'no file uploaded' });

    const rawPath = String(req.body.path || req.file.originalname || '').replace(/\\/g, '/');
    const declaredPath = rawPath.split('/').filter(Boolean).join('/');
    if (!declaredPath || declaredPath.includes('..') || path.isAbsolute(declaredPath)) {
      fs.unlinkSync(req.file.path);
      return res.status(400).json({ error: 'invalid file path' });
    }
    const projectRoot = path.resolve(projectDir);
    const targetPath = path.resolve(projectRoot, declaredPath);
    if (path.relative(projectRoot, targetPath).startsWith('..') || path.relative(projectRoot, targetPath) === '') {
      fs.unlinkSync(req.file.path);
      return res.status(400).json({ error: 'invalid file path' });
    }
    const targetDir = path.dirname(targetPath);

    if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });
    fs.renameSync(req.file.path, targetPath);

    projectSvc.upsertProjectFile({
      projectId: proj.id,
      filePath: declaredPath,
      diskPath: targetPath,
      size: req.file.size,
      userId: u.id,
    });

    logger.info('file uploaded', { project: proj.id, path: declaredPath });
    res.json({ ok: true, path: declaredPath, size: req.file.size });
  });
});

// Download / view raw file
router.get('/:id/files/:fileId', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'not found' });
  if (!canAccessProject(req.session.user, proj)) return res.status(403).json({ error: 'forbidden' });
  const fileRow = require('../lib/db').get().prepare(
    'SELECT * FROM project_files WHERE id = ? AND project_id = ?'
  ).get(req.params.fileId, proj.id);
  if (!fileRow || !fs.existsSync(fileRow.disk_path)) {
    return res.status(404).json({ error: 'file not found' });
  }
  res.sendFile(fileRow.disk_path);
});

// Delete file
router.post('/:id/files/:fileId/delete', (req, res) => {
  const u = req.session.user;
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'not found' });
  if (proj.owner_id !== u.id && u.role !== 'admin') return res.status(403).json({ error: 'forbidden' });

  const fileRow = require('../lib/db').get().prepare(
    'SELECT * FROM project_files WHERE id = ? AND project_id = ?'
  ).get(req.params.fileId, proj.id);
  if (!fileRow) return res.status(404).json({ error: 'file not found' });

  try { fs.unlinkSync(fileRow.disk_path); } catch (_) {}
  require('../lib/db').get().prepare('DELETE FROM project_files WHERE id = ?').run(fileRow.id);
  res.json({ ok: true });
});

// ── Automation endpoints ──────────────────────────────────────────────────────

/**
 * POST /projects/:id/open
 * Activates the project session: warms the local tooling cache by running
 * any onOpen automation hooks declared in the project settings file.
 */
router.post('/:id/open', ensureCsrf, (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });
  if (!canAccessProject(req.session.user, proj)) return res.status(403).json({ error: 'forbidden' });

  const projectDir = projectDirFor(proj.id);
  const automations = automationSvc.runOnOpenAutomations(projectDir);

  logger.info('project opened', { id: proj.id, hooksRan: automations.ran });
  res.json({ ok: true, project: { id: proj.id, name: proj.name }, automations });
});

/**
 * POST /projects/:id/sync
 * Pulls latest remote state and runs onSync hooks.
 * Equivalent to `git pull && run-hooks`.
 */
router.post('/:id/sync', ensureCsrf, (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });
  if (!canAccessProject(req.session.user, proj)) return res.status(403).json({ error: 'forbidden' });

  const projectDir = projectDirFor(proj.id);
  const automations = automationSvc.runOnSyncAutomations(projectDir);

  res.json({ ok: true, project: { id: proj.id }, automations });
});

/**
 * POST /projects/:id/format
 * Runs a code formatter (prettier / black / rustfmt) against the project tree.
 * The formatter name is validated against an allowlist before execution.
 */
router.post('/:id/format', ensureCsrf, (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });
  if (!canAccessProject(req.session.user, proj)) return res.status(403).json({ error: 'forbidden' });
  // Disabled: prettier/black/rustfmt all execute project-local plugins or
  // load attacker-controlled config files (.prettierrc, pyproject.toml,
  // rustfmt.toml). Running them with the API process's privileges yields
  // command execution as the API user from any project owner. Use a
  // sandboxed worker (container, firejail) before re-enabling.
  return res.status(501).json({ error: 'In-process formatters are disabled on this deployment' });
});

/**
 * POST /projects/:id/lint
 * Runs a linter pass and returns the output. Results are cached per-commit
 * when a git SHA header is provided.
 */
router.post('/:id/lint', ensureCsrf, (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });
  if (!canAccessProject(req.session.user, proj)) return res.status(403).json({ error: 'forbidden' });
  // Disabled for the same reason as /format above: eslint/pylint/clippy
  // load project-local plugins and configuration that execute arbitrary
  // code from the owner's uploaded files.
  return res.status(501).json({ error: 'In-process linters are disabled on this deployment' });
});

module.exports = router;
