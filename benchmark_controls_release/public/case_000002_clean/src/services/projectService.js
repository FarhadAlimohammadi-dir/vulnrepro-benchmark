const path = require('path');
const fs = require('fs');
const db = require('../lib/db');
const { slugify, ensureProjectDir, projectDirFor } = require('../lib/util');
const logger = require('../lib/logger');

function listWorkspaceProjects(workspaceId, { archived = false } = {}) {
  return db.get().prepare(
    `SELECT p.*, u.username AS owner_name
     FROM projects p
     LEFT JOIN users u ON p.owner_id = u.id
     WHERE p.workspace_id = ? AND p.archived = ?
     ORDER BY p.created_at DESC`
  ).all(workspaceId, archived ? 1 : 0);
}

function getProject(id) {
  return db.get().prepare(
    `SELECT p.*, u.username AS owner_name, w.name AS workspace_name
     FROM projects p
     LEFT JOIN users u ON p.owner_id = u.id
     LEFT JOIN workspaces w ON p.workspace_id = w.id
     WHERE p.id = ?`
  ).get(id);
}

function createProject({ workspaceId, name, description, language, ownerId }) {
  const slug = slugify(name);
  const result = db.get().prepare(
    `INSERT INTO projects (workspace_id, name, slug, owner_id, description, language)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).run(workspaceId, name, slug, ownerId, description || '', language || '');
  const id = result.lastInsertRowid;
  ensureProjectDir(id);
  return getProject(id);
}

function updateProject(id, { name, description, language }) {
  db.get().prepare(
    'UPDATE projects SET name=?, description=?, language=? WHERE id=?'
  ).run(name, description, language, id);
  return getProject(id);
}

function archiveProject(id) {
  db.get().prepare('UPDATE projects SET archived=1 WHERE id=?').run(id);
}

function listProjectFiles(projectId) {
  return db.get().prepare(
    'SELECT * FROM project_files WHERE project_id = ? ORDER BY path'
  ).all(projectId);
}

function upsertProjectFile({ projectId, filePath, diskPath, size, userId }) {
  db.get().prepare(
    `INSERT INTO project_files (project_id, path, disk_path, size, uploaded_by)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(project_id, path) DO UPDATE SET disk_path=excluded.disk_path, size=excluded.size`
  ).run(projectId, filePath, diskPath, size, userId);
}

function getSettingsFilePath(projectId) {
  const dir = projectDirFor(projectId);
  const claspaceDir = path.join(dir, '.claspace');
  const settingsPath = path.join(claspaceDir, 'settings.json');
  if (fs.existsSync(settingsPath)) return settingsPath;
  return null;
}

module.exports = {
  listWorkspaceProjects,
  getProject,
  createProject,
  updateProject,
  archiveProject,
  listProjectFiles,
  upsertProjectFile,
  getSettingsFilePath,
};