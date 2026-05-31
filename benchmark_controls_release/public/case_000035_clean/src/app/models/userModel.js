'use strict';

const { getDB } = require('./database');
const crypto = require('crypto');

function hashPassword(pwd) {
  return crypto.createHash('sha256').update(pwd + 'gw-salt-2024').digest('hex');
}

function findByUsername(username) {
  return getDB().prepare('SELECT * FROM users WHERE username = ?').get(username);
}

function findById(id) {
  return getDB().prepare('SELECT * FROM users WHERE id = ?').get(id);
}

function listUsers({ page = 1, pageSize = 20, search = '', department = '' } = {}) {
  const offset = (page - 1) * pageSize;
  let query = 'SELECT id, username, employee_name, department, title, enabled, roles, last_login, created_at FROM users WHERE 1=1';
  const params = [];

  if (search) {
    query += ' AND (username LIKE ? OR employee_name LIKE ?)';
    params.push(`%${search}%`, `%${search}%`);
  }
  if (department) {
    query += ' AND department = ?';
    params.push(department);
  }
  query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(pageSize, offset);

  const rows = getDB().prepare(query).all(...params);

  let countQuery = 'SELECT COUNT(*) as total FROM users WHERE 1=1';
  const countParams = params.slice(0, params.length - 2);
  if (search) countQuery += ' AND (username LIKE ? OR employee_name LIKE ?)';
  if (department) countQuery += ' AND department = ?';

  const { total } = getDB().prepare(countQuery).get(...countParams);
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

function createUser({ username, password, employee_name, department, title, roles, enabled }) {
  const db = getDB();
  const hashed = hashPassword(password);
  const result = db.prepare(
    `INSERT INTO users (username, password, employee_name, department, title, enabled, roles)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(username, hashed, employee_name || '', department || 'General', title || '', enabled !== undefined ? enabled : 1, roles);
  return result.lastInsertRowid;
}

function updateUser(id, fields) {
  const db = getDB();
  const allowed = ['employee_name', 'department', 'title', 'phone', 'enabled', 'roles'];
  const sets = [];
  const vals = [];
  for (const [k, v] of Object.entries(fields)) {
    if (allowed.includes(k)) {
      sets.push(`${k} = ?`);
      vals.push(v);
    }
  }
  if (sets.length === 0) return;
  sets.push('updated_at = CURRENT_TIMESTAMP');
  vals.push(id);
  db.prepare(`UPDATE users SET ${sets.join(', ')} WHERE id = ?`).run(...vals);
}

function updateLastLogin(id) {
  getDB().prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?').run(id);
}

function verifyPassword(stored, provided) {
  return stored === hashPassword(provided);
}

module.exports = {
  hashPassword,
  findByUsername,
  findById,
  listUsers,
  createUser,
  updateUser,
  updateLastLogin,
  verifyPassword
};