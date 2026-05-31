'use strict';

const { db } = require('../db');

/**
 * Returns paginated public snippets.
 */
function getPublicSnippets({ page = 1, perPage = 20, language = null } = {}) {
  let where = 'WHERE s.public = 1';
  const params = [];
  if (language) { where += ' AND s.language = ?'; params.push(language); }
  const total = db.prepare(`SELECT COUNT(*) as c FROM snippets s ${where}`).get(...params).c;
  const rows  = db.prepare(
    `SELECT s.id, s.title, s.language, s.view_count, u.username, s.created_at
     FROM snippets s JOIN users u ON s.owner_id = u.id
     ${where} ORDER BY s.created_at DESC LIMIT ? OFFSET ?`
  ).all(...params, perPage, (page - 1) * perPage);
  return { rows, total, pages: Math.ceil(total / perPage) };
}

/**
 * Returns a single snippet by ID, including author info.
 */
function getSnippetById(id) {
  return db.prepare(
    `SELECT s.*, u.username FROM snippets s JOIN users u ON s.owner_id = u.id WHERE s.id = ?`
  ).get(id) || null;
}

/**
 * Returns star count for a snippet.
 */
function getStarCount(snippetId) {
  return db.prepare('SELECT COUNT(*) as c FROM stars WHERE snippet_id=?').get(snippetId).c;
}

module.exports = { getPublicSnippets, getSnippetById, getStarCount };