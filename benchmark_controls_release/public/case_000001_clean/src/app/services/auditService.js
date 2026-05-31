'use strict';

let _db;

function setDb(db) {
  _db = db;
}

function writeAudit(actor, action, target, detail, ip) {
  if (!_db) return;
  try {
    _db.prepare(
      'INSERT INTO audit_log (actor, action, target, detail, ip) VALUES (?,?,?,?,?)'
    ).run(actor || 'system', action, target || '', detail || '{}', ip || '');
  } catch (e) {
    console.error('[audit] write failed:', e.message);
  }
}

function recentAudit(limit) {
  if (!_db) return [];
  limit = Math.min(parseInt(limit) || 50, 200);
  return _db.prepare(
    'SELECT * FROM audit_log ORDER BY id DESC LIMIT ?'
  ).all(limit);
}

module.exports = { setDb, writeAudit, recentAudit };