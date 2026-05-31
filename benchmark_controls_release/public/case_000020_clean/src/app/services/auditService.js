'use strict';

const { db } = require('../db');

function log(userId, action, detail = '') {
  db.prepare(
    'INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)'
  ).run(userId, action, detail);
}

function getForUser(userId, limit = 20) {
  return db.prepare(
    'SELECT * FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
  ).all(userId, limit);
}

function getAll({ page = 1, pageSize = 25 } = {}) {
  const offset = (page - 1) * pageSize;
  const rows = db.prepare(
    'SELECT al.*, u.username FROM audit_log al LEFT JOIN users u ON u.id = al.user_id ORDER BY al.created_at DESC LIMIT ? OFFSET ?'
  ).all(pageSize, offset);
  const total = db.prepare('SELECT COUNT(*) AS n FROM audit_log').get().n;
  return { rows, total, page, pageSize, totalPages: Math.ceil(total / pageSize) };
}

module.exports = { log, getForUser, getAll };