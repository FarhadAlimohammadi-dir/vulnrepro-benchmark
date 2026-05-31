'use strict';

const { getDB } = require('./database');

function listByUser(userId, { page = 1, pageSize = 15 } = {}) {
  const offset = (page - 1) * pageSize;
  const rows = getDB().prepare(
    `SELECT ar.*, u.employee_name as reviewer_name
     FROM access_requests ar
     LEFT JOIN users u ON ar.reviewer_id = u.id
     WHERE ar.user_id = ?
     ORDER BY ar.created_at DESC LIMIT ? OFFSET ?`
  ).all(userId, pageSize, offset);
  const { total } = getDB().prepare('SELECT COUNT(*) as total FROM access_requests WHERE user_id = ?').get(userId);
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

function listAll({ page = 1, pageSize = 25, status = '', search = '' } = {}) {
  const offset = (page - 1) * pageSize;
  let q = `SELECT ar.*, u.employee_name, u.username
           FROM access_requests ar
           JOIN users u ON ar.user_id = u.id WHERE 1=1`;
  const params = [];

  if (status) { q += ' AND ar.status = ?'; params.push(status); }
  if (search) { q += ' AND (ar.title LIKE ? OR ar.system_name LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  q += ' ORDER BY ar.created_at DESC LIMIT ? OFFSET ?';
  params.push(pageSize, offset);

  const rows = getDB().prepare(q).all(...params);
  const { total } = getDB().prepare('SELECT COUNT(*) as total FROM access_requests').get();
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

function createRequest({ user_id, title, description, system_name, access_level }) {
  const result = getDB().prepare(
    `INSERT INTO access_requests (user_id, title, description, system_name, access_level)
     VALUES (?, ?, ?, ?, ?)`
  ).run(user_id, title, description || '', system_name, access_level || 'READ');
  return result.lastInsertRowid;
}

function updateStatus(id, { status, reviewer_id, review_notes }) {
  getDB().prepare(
    `UPDATE access_requests SET status = ?, reviewer_id = ?, review_notes = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
     WHERE id = ?`
  ).run(status, reviewer_id, review_notes || '', id);
}

function findById(id) {
  return getDB().prepare('SELECT * FROM access_requests WHERE id = ?').get(id);
}

function countByStatus() {
  return getDB().prepare(
    `SELECT status, COUNT(*) as count FROM access_requests GROUP BY status`
  ).all();
}

module.exports = { listByUser, listAll, createRequest, updateStatus, findById, countByStatus };