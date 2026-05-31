'use strict';

const db = require('../models/db');

function getByCredentials(username, password) {
  return db.prepare('SELECT * FROM users WHERE username = ? AND password = ?').get(username, password);
}

function getById(id) {
  return db.prepare('SELECT id, username, role, email, display_name, created_at FROM users WHERE id = ?').get(id);
}

function listAll() {
  return db.prepare('SELECT id, username, role, email, display_name, created_at FROM users ORDER BY id ASC').all();
}

function update(id, fields) {
  const allowed = ['email', 'display_name'];
  const sets = [];
  const vals = [];
  for (const k of allowed) {
    if (fields[k] !== undefined) {
      sets.push(`${k} = ?`);
      vals.push(fields[k]);
    }
  }
  if (sets.length === 0) return;
  vals.push(id);
  db.prepare(`UPDATE users SET ${sets.join(', ')} WHERE id = ?`).run(...vals);
}

function setRole(id, role) {
  if (!['admin', 'member', 'viewer'].includes(role)) throw new Error('Invalid role');
  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, id);
}

module.exports = { getByCredentials, getById, listAll, update, setRole };