const express = require('express');
const path = require('path');
const fs = require('fs');
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
  const files = projectSvc.listProjectFiles(proj.id);
  const hasSettings = !!projectSvc.getSettingsFilePath(proj.id);
  res.render('project_detail', { proj, files, hasSettings });
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
    filename(req2, file, cb) { cb(null, file.originalname); },
  });
  const uploadForProject = multer({ storage: storageForProject, limits: { fileSize: 2 * 1024 * 1024 } }).single('file');

  uploadForProject(req, res, (err) => {
    if (err) return res.status(400).json({ error: err.message });
    if (!req.file) return res.status(400).json({ error: 'no file uploaded' });

    // Handle nested path like .claspace/settings.json
    const declaredPath = (req.body.path || req.file.originalname).replace(/\.\./g, '').replace(/^\//, '');
    const targetPath = path.join(projectDir, declaredPath);
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
router.post('/:id/open', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });

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
router.post('/:id/sync', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });

  const projectDir = projectDirFor(proj.id);
  const automations = automationSvc.runOnSyncAutomations(projectDir);

  res.json({ ok: true, project: { id: proj.id }, automations });
});

/**
 * POST /projects/:id/format
 * Runs a code formatter (prettier / black / rustfmt) against the project tree.
 * The formatter name is validated against an allowlist before execution.
 */
router.post('/:id/format', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });

  const allowed = { prettier: 'npx prettier --write .', black: 'black .', rustfmt: 'cargo fmt' };
  const formatterKey = (req.body.formatter || 'prettier').toLowerCase();

  if (!allowed[formatterKey]) {
    return res.status(400).json({ error: 'unknown formatter', allowed: Object.keys(allowed) });
  }

  const projectDir = projectDirFor(proj.id);
  if (!fs.existsSync(projectDir)) {
    return res.status(400).json({ error: 'project directory not initialised' });
  }

  let stdout = '';
  let exitCode = 0;
  try {
    const { execSync } = require('child_process');
    stdout = execSync(allowed[formatterKey], {
      cwd: projectDir,
      timeout: 30000,
      env: { PATH: process.env.PATH },
    }).toString();
  } catch (e) {
    exitCode = e.status || 1;
    stdout = e.stderr ? e.stderr.toString() : e.message;
  }

  res.json({ ok: exitCode === 0, formatter: formatterKey, stdout });
});

/**
 * POST /projects/:id/lint
 * Runs a linter pass and returns the output. Results are cached per-commit
 * when a git SHA header is provided.
 */
router.post('/:id/lint', (req, res) => {
  const proj = projectSvc.getProject(req.params.id);
  if (!proj) return res.status(404).json({ error: 'project not found' });

  const linters = { eslint: 'npx eslint .', pylint: 'pylint .', clippy: 'cargo clippy' };
  const linterKey = (req.body.linter || 'eslint').toLowerCase();

  if (!linters[linterKey]) {
    return res.status(400).json({ error: 'unknown linter' });
  }

  const projectDir = projectDirFor(proj.id);
  let output = '';
  let exitCode = 0;
  try {
    const { execSync } = require('child_process');
    output = execSync(linters[linterKey], {
      cwd: projectDir,
      timeout: 60000,
      env: { PATH: process.env.PATH },
    }).toString();
  } catch (e) {
    exitCode = e.status || 1;
    output = e.stderr ? e.stderr.toString() : e.message;
  }

  res.json({ ok: exitCode === 0, linter: linterKey, output });
});

module.exports = router;