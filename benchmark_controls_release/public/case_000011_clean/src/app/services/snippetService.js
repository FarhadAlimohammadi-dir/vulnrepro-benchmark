'use strict';
const db = require('../db');

function listSnippets({ page = 1, perPage = 15, language = null, search = null, userId = null } = {}) {
  const offset = (page - 1) * perPage;
  const conditions = [];
  const params = [];

  if (language) { conditions.push('s.language = ?'); params.push(language); }
  if (search)   { conditions.push('(s.title LIKE ? OR s.description LIKE ?)'); params.push(`%${search}%`, `%${search}%`); }
  if (userId)   { conditions.push('s.owner_id = ?'); params.push(userId); }

  const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';

  const countRow = db.prepare(
    `SELECT COUNT(*) AS n FROM snippets s ${where}`
  ).get(...params);
  const total = countRow ? countRow.n : 0;

  params.push(perPage, offset);
  const rows = db.prepare(
    `SELECT s.id, s.title, s.language, s.description, s.stars, s.created_at, s.updated_at, u.username
     FROM snippets s
     JOIN users u ON s.owner_id = u.id
     ${where}
     ORDER BY s.updated_at DESC
     LIMIT ? OFFSET ?`
  ).all(...params);

  return { rows, total, page, perPage, pages: Math.max(1, Math.ceil(total / perPage)) };
}

function getSnippetById(id) {
  return db.prepare(
    `SELECT s.*, u.username, u.avatar_color
     FROM snippets s
     JOIN users u ON s.owner_id = u.id
     WHERE s.id = ?`
  ).get(id);
}

function createSnippet(ownerId, { title, content, language, description }) {
  const result = db.prepare(
    'INSERT INTO snippets (owner_id, title, content, language, description) VALUES (?, ?, ?, ?, ?)'
  ).run(ownerId, title.slice(0, 200), content.slice(0, 50000), (language || 'text').slice(0, 30), (description || '').slice(0, 500));

  const sid = result.lastInsertRowid;
  db.prepare('INSERT INTO snippet_history (snippet_id, version, summary, author_id) VALUES (?, ?, ?, ?)')
    .run(sid, 1, 'Created', ownerId);
  return sid;
}

function updateSnippet(id, ownerId, { title, content, language, description }) {
  const snippet = db.prepare('SELECT id FROM snippets WHERE id = ? AND owner_id = ?').get(id, ownerId);
  if (!snippet) return null;

  db.prepare(
    'UPDATE snippets SET title = ?, content = ?, language = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
  ).run(title.slice(0, 200), content.slice(0, 50000), (language || 'text').slice(0, 30), (description || '').slice(0, 500), id);

  const last = db.prepare('SELECT MAX(version) AS v FROM snippet_history WHERE snippet_id = ?').get(id);
  const nextVer = (last && last.v) ? last.v + 1 : 2;
  db.prepare('INSERT INTO snippet_history (snippet_id, version, summary, author_id) VALUES (?, ?, ?, ?)')
    .run(id, nextVer, 'Edited', ownerId);
  return id;
}

function deleteSnippet(id, ownerId) {
  const snippet = db.prepare('SELECT id FROM snippets WHERE id = ?').get(id);
  if (!snippet) return false;
  db.prepare('DELETE FROM snippets WHERE id = ?').run(id);
  return true;
}

function getComments(snippetId) {
  return db.prepare(
    `SELECT c.id, c.body, c.created_at, u.username, u.avatar_color
     FROM snippet_comments c
     JOIN users u ON c.author_id = u.id
     WHERE c.snippet_id = ?
     ORDER BY c.created_at ASC`
  ).all(snippetId);
}

function addComment(snippetId, authorId, body) {
  return db.prepare('INSERT INTO snippet_comments (snippet_id, author_id, body) VALUES (?, ?, ?)')
    .run(snippetId, authorId, body.slice(0, 2000));
}

module.exports = { listSnippets, getSnippetById, createSnippet, updateSnippet, deleteSnippet, getComments, addComment };