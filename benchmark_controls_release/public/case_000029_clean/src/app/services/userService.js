'use strict';

const db = require('../db');

function findByCredentials(username, password) {
  if (!username || !password) return null;
  return db.prepare("SELECT id, username, role, display_name, email FROM users WHERE username=? AND password=?").get(username, password);
}

function findById(id) {
  return db.prepare("SELECT id, username, role, display_name, email, created_at FROM users WHERE id=?").get(id);
}

function listUsers({ limit = 30, offset = 0 } = {}) {
  return db.prepare(`
    SELECT id, username, role, display_name, email, created_at
    FROM users ORDER BY id LIMIT ? OFFSET ?
  `).all(limit, offset);
}

function countUsers() {
  return db.prepare("SELECT COUNT(*) AS n FROM users").get().n;
}

function updateProfile(id, { display_name, email }) {
  const dn = (display_name || '').slice(0, 80);
  const em = (email || '').slice(0, 120);
  db.prepare("UPDATE users SET display_name=?, email=? WHERE id=?").run(dn, em, id);
}

function updatePassword(id, newPassword) {
  if (!newPassword || newPassword.length < 6) throw new Error('Password too short');
  db.prepare("UPDATE users SET password=? WHERE id=?").run(newPassword, id);
}

function verifyPassword(id, password) {
  if (!id || !password) return false;
  const row = db.prepare("SELECT id FROM users WHERE id=? AND password=?").get(id, password);
  return Boolean(row);
}

module.exports = { findByCredentials, findById, listUsers, countUsers, updateProfile, updatePassword, verifyPassword };
