'use strict';

const db = require('../models/db');

function listForProject(projectId) {
  return db.prepare('SELECT * FROM tasks WHERE project_id = ? ORDER BY id ASC').all(projectId);
}

function create(projectId, title, assignee, priority) {
  priority = ['low', 'medium', 'high'].includes(priority) ? priority : 'medium';
  const info = db.prepare(
    'INSERT INTO tasks (project_id, title, assignee, priority, done) VALUES (?, ?, ?, ?, 0)'
  ).run(projectId, title, assignee, priority);
  return info.lastInsertRowid;
}

function markDone(id) {
  db.prepare('UPDATE tasks SET done = 1 WHERE id = ?').run(id);
}

function remove(id) {
  db.prepare('DELETE FROM tasks WHERE id = ?').run(id);
}

function listAll(limit) {
  limit = Math.min(parseInt(limit) || 50, 500);
  return db.prepare(
    `SELECT t.*, p.name AS project_name FROM tasks t
     JOIN projects p ON p.id = t.project_id
     ORDER BY t.id DESC LIMIT ?`
  ).all(limit);
}

function belongsToProject(taskId, projectId) {
  const row = db.prepare('SELECT 1 FROM tasks WHERE id = ? AND project_id = ?').get(taskId, projectId);
  return !!row;
}

module.exports = { listForProject, create, markDone, remove, listAll, belongsToProject };