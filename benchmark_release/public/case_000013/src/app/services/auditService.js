'use strict';

const db = require('../db');

function record(actorId, actorName, action, target, ip) {
  db.prepare(
    'INSERT INTO audit_log (actor_id, actor_name, action, target, ip) VALUES (?, ?, ?, ?, ?)'
  ).run(actorId || null, actorName || 'system', action, target || null, ip || null);
}

function getRecentEvents(limit = 50) {
  return db.prepare(
    'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?'
  ).all(limit);
}

function getEventsForActor(actorId, limit = 30) {
  return db.prepare(
    'SELECT * FROM audit_log WHERE actor_id = ? ORDER BY created_at DESC LIMIT ?'
  ).all(actorId, limit);
}

module.exports = { record, getRecentEvents, getEventsForActor };