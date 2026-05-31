const db = require('../lib/db');
const logger = require('../lib/logger');

function listUserWorkspaces(userId, role) {
  if (role === 'admin') {
    return db.get().prepare(
      `SELECT w.*, u.username AS owner_name,
              (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id AND p.archived=0) AS project_count
       FROM workspaces w
       LEFT JOIN users u ON w.owner_id = u.id
       ORDER BY w.created_at DESC`
    ).all();
  }
  return db.get().prepare(
    `SELECT DISTINCT w.*, u.username AS owner_name,
            (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id AND p.archived=0) AS project_count
     FROM workspaces w
     LEFT JOIN users u ON w.owner_id = u.id
     LEFT JOIN workspace_members m ON m.workspace_id = w.id
     WHERE w.owner_id = ? OR m.user_id = ? OR w.visibility = 'public'
     ORDER BY w.created_at DESC`
  ).all(userId, userId);
}

function getWorkspace(id) {
  return db.get().prepare(
    `SELECT w.*, u.username AS owner_name FROM workspaces w
     LEFT JOIN users u ON w.owner_id = u.id WHERE w.id = ?`
  ).get(id);
}

function createWorkspace({ name, description, visibility, ownerId }) {
  const r = db.get().prepare(
    'INSERT INTO workspaces (name, owner_id, description, visibility) VALUES (?, ?, ?, ?)'
  ).run(name, ownerId, description || '', visibility || 'private');
  return getWorkspace(r.lastInsertRowid);
}

function updateWorkspace(id, { name, description, visibility }) {
  db.get().prepare(
    'UPDATE workspaces SET name=?, description=?, visibility=? WHERE id=?'
  ).run(name, description, visibility, id);
  return getWorkspace(id);
}

function deleteWorkspace(id) {
  db.get().prepare('DELETE FROM workspaces WHERE id=?').run(id);
}

function getMembers(workspaceId) {
  return db.get().prepare(
    `SELECT m.*, u.username, u.email FROM workspace_members m
     JOIN users u ON m.user_id = u.id WHERE m.workspace_id = ?`
  ).all(workspaceId);
}

module.exports = { listUserWorkspaces, getWorkspace, createWorkspace, updateWorkspace, deleteWorkspace, getMembers };