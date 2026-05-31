'use strict';

const db = require('../models/db');
const logger = require('./logger');

function record(userId, action, detail) {
  try {
    db.prepare(
      'INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)'
    ).run(userId, action, detail || '', new Date().toISOString());
  } catch (e) {
    logger.error(`Audit log write failed: ${e.message}`);
  }
}

function recent(limit) {
  limit = Math.min(parseInt(limit) || 50, 200);
  return db.prepare(
    `SELECT a.*, u.username FROM audit_log a
     LEFT JOIN users u ON u.id = a.user_id
     ORDER BY a.id DESC LIMIT ?`
  ).all(limit);
}

module.exports = { record, recent };