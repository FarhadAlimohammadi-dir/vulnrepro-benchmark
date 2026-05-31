'use strict';

const db = require('../db');

const VALID_LANGS = ['javascript', 'typescript', 'python', 'go', 'rust', 'ruby', 'java', 'csharp'];

function listUserProjects(userId, { page = 1, limit = 10 } = {}) {
  const offset = (page - 1) * limit;
  const rows = db.prepare(
    `SELECT p.*, u.username AS owner_name
       FROM projects p
       JOIN users u ON p.owner_id = u.id
      WHERE p.owner_id = ?
      ORDER BY p.updated_at DESC
      LIMIT ? OFFSET ?`
  ).all(userId, limit, offset);
  const total = db.prepare('SELECT COUNT(*) AS n FROM projects WHERE owner_id = ?').get(userId).n;
  return { rows, total, page, limit };
}

function getProject(projectId, userId) {
  return db.prepare(
    'SELECT p.*, u.username AS owner_name FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.id = ? AND p.owner_id = ?'
  ).get(projectId, userId);
}

function createProject({ name, description, lang, visibility, ownerId }) {
  if (!name || name.length > 80) throw new Error('Invalid project name');
  if (!VALID_LANGS.includes(lang))  throw new Error('Unsupported language: ' + lang);
  const vis = visibility === 'public' ? 'public' : 'private';
  const info = db.prepare(
    'INSERT INTO projects (name, description, lang, visibility, owner_id) VALUES (?, ?, ?, ?, ?)'
  ).run(name.trim(), (description || '').trim(), lang, vis, ownerId);
  return info.lastInsertRowid;
}

function updateProject(projectId, userId, { name, description }) {
  if (name && name.length > 80) throw new Error('Name too long');
  db.prepare(
    `UPDATE projects
        SET name = COALESCE(?, name),
            description = COALESCE(?, description),
            updated_at = CURRENT_TIMESTAMP
      WHERE id = ? AND owner_id = ?`
  ).run(name || null, description || null, projectId, userId);
}

function deleteProject(projectId, userId) {
  db.prepare('DELETE FROM projects WHERE id = ? AND owner_id = ?').run(projectId, userId);
}

function searchProjects(userId, query) {
  if (!query || typeof query !== 'string' || query.length > 128) return [];
  const term = '%' + query.replace(/[%_]/g, '\\$&') + '%';
  return db.prepare(
    `SELECT id, name, description, lang, updated_at
       FROM projects
      WHERE owner_id = ? AND (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')`
  ).all(userId, term, term);
}

function listSnippets(projectId, userId) {
  const project = getProject(projectId, userId);
  if (!project) return null;
  return db.prepare(
    `SELECT s.*, u.username AS author_name
       FROM snippets s
       JOIN users u ON s.author_id = u.id
      WHERE s.project_id = ?
      ORDER BY s.created_at DESC`
  ).all(projectId);
}

function addSnippet({ projectId, title, lang, body, authorId }) {
  if (!title || title.length > 120) throw new Error('Invalid snippet title');
  if (!VALID_LANGS.includes(lang))  throw new Error('Unsupported language');
  if (!body || body.length > 32_000) throw new Error('Body too large');
  const info = db.prepare(
    'INSERT INTO snippets (project_id, title, lang, body, author_id) VALUES (?, ?, ?, ?, ?)'
  ).run(projectId, title.trim(), lang, body, authorId);
  return info.lastInsertRowid;
}

module.exports = { listUserProjects, getProject, createProject, updateProject, deleteProject, searchProjects, listSnippets, addSnippet, VALID_LANGS };