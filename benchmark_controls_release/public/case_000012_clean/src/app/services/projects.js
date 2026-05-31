'use strict';

const db = require('../models/db');

function listForUser(userId) {
  return db.prepare(
    `SELECT p.*, u.username AS owner_name,
       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS task_count,
       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.done = 0) AS open_count
     FROM projects p
     JOIN users u ON u.id = p.owner_id
     WHERE p.owner_id = ? OR p.id IN (
       SELECT DISTINCT project_id FROM tasks WHERE assignee = (
         SELECT username FROM users WHERE id = ?
       )
     )
     ORDER BY p.id DESC`
  ).all(userId, userId);
}

function getById(id) {
  return db.prepare('SELECT p.*, u.username AS owner_name FROM projects p JOIN users u ON u.id = p.owner_id WHERE p.id = ?').get(id);
}

function isVisibleTo(project, userId, role) {
  if (!project || !userId) return false;
  if (role === 'admin') return true;
  if (project.owner_id === userId) return true;
  const row = db.prepare(
    `SELECT 1 FROM tasks t JOIN users u ON u.username = t.assignee
     WHERE t.project_id = ? AND u.id = ? LIMIT 1`
  ).get(project.id, userId);
  return !!row;
}

function create(name, description, ownerId) {
  const info = db.prepare(
    'INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)'
  ).run(name, description, ownerId);
  return info.lastInsertRowid;
}

function update(id, name, description) {
  db.prepare('UPDATE projects SET name = ?, description = ? WHERE id = ?').run(name, description, id);
}

function remove(id) {
  db.prepare('DELETE FROM tasks WHERE project_id = ?').run(id);
  db.prepare('DELETE FROM projects WHERE id = ?').run(id);
}

function search(query, page, pageSize) {
  const offset = (page - 1) * pageSize;
  const pat = `%${query}%`;
  const rows = db.prepare(
    `SELECT p.*, u.username AS owner_name FROM projects p
     JOIN users u ON u.id = p.owner_id
     WHERE p.name LIKE ? OR p.description LIKE ?
     ORDER BY p.id DESC LIMIT ? OFFSET ?`
  ).all(pat, pat, pageSize, offset);
  const total = db.prepare(
    'SELECT COUNT(*) AS cnt FROM projects WHERE name LIKE ? OR description LIKE ?'
  ).get(pat, pat).cnt;
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

// Scoped search: admins see everything, everyone else sees only projects
// they own or are an assignee on. Mirrors the rule used by isVisibleTo.
function searchVisibleTo(query, userId, role, page, pageSize) {
  const offset = (page - 1) * pageSize;
  const pat = `%${query}%`;
  if (role === 'admin') {
    return search(query, page, pageSize);
  }
  const rows = db.prepare(
    `SELECT p.*, u.username AS owner_name FROM projects p
     JOIN users u ON u.id = p.owner_id
     WHERE (p.name LIKE ? OR p.description LIKE ?)
       AND (
         p.owner_id = ?
         OR p.id IN (
           SELECT DISTINCT t.project_id FROM tasks t
           JOIN users au ON au.username = t.assignee
           WHERE au.id = ?
         )
       )
     ORDER BY p.id DESC LIMIT ? OFFSET ?`
  ).all(pat, pat, userId, userId, pageSize, offset);
  const total = db.prepare(
    `SELECT COUNT(*) AS cnt FROM projects p
     WHERE (p.name LIKE ? OR p.description LIKE ?)
       AND (
         p.owner_id = ?
         OR p.id IN (
           SELECT DISTINCT t.project_id FROM tasks t
           JOIN users au ON au.username = t.assignee
           WHERE au.id = ?
         )
       )`
  ).get(pat, pat, userId, userId).cnt;
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

module.exports = { listForUser, getById, create, update, remove, search, searchVisibleTo, isVisibleTo };