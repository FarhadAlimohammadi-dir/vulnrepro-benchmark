'use strict';

const { db } = require('../db');

function log(actorId, action, detail = '') {
  try {
    db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
      .run(actorId, action, String(detail).slice(0, 500));
  } catch (e) {
    console.error('[audit] write failed:', e.message);
  }
}

function getRecent(limit = 100) {
  return db.prepare(
    `SELECT l.id, l.action, l.detail, l.created_at, u.username
     FROM audit_log l LEFT JOIN users u ON l.actor_id = u.id
     ORDER BY l.created_at DESC LIMIT ?`
  ).all(limit);
}

module.exports = { log, getRecent };