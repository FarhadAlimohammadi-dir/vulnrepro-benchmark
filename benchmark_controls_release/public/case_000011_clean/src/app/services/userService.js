'use strict';
const db = require('../db');

function getUserById(id) {
  return db.prepare('SELECT id, username, email, role, bio, avatar_color, created_at FROM users WHERE id = ?').get(id);
}

function getUserByUsername(username) {
  return db.prepare('SELECT id, username, email, role, bio, avatar_color, created_at FROM users WHERE username = ?').get(username);
}

function updateProfile(id, { email, bio, avatar_color }) {
  db.prepare('UPDATE users SET email = ?, bio = ?, avatar_color = ? WHERE id = ?')
    .run((email || '').slice(0, 120), (bio || '').slice(0, 300), (avatar_color || '#4f46e5').slice(0, 20), id);
}

function listUsers({ page = 1, perPage = 20 } = {}) {
  const offset = (page - 1) * perPage;
  const total = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  const rows = db.prepare(
    'SELECT id, username, email, role, created_at FROM users ORDER BY created_at ASC LIMIT ? OFFSET ?'
  ).all(perPage, offset);
  return { rows, total, page, perPage, pages: Math.max(1, Math.ceil(total / perPage)) };
}

function getAuditLog({ page = 1, perPage = 30 } = {}) {
  const offset = (page - 1) * perPage;
  const total = db.prepare('SELECT COUNT(*) AS n FROM audit_log').get().n;
  const rows = db.prepare(
    `SELECT al.id, al.action, al.resource_type, al.resource_id, al.meta, al.ip, al.created_at, u.username
     FROM audit_log al
     LEFT JOIN users u ON al.user_id = u.id
     ORDER BY al.created_at DESC
     LIMIT ? OFFSET ?`
  ).all(perPage, offset);
  return { rows, total, page, perPage, pages: Math.max(1, Math.ceil(total / perPage)) };
}

module.exports = { getUserById, getUserByUsername, updateProfile, listUsers, getAuditLog };