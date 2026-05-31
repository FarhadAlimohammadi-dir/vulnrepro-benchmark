'use strict';

const { v4: uuidv4 } = require('uuid');

function logAuditEvent(db, actorId, action, resourceType, resourceId, details, ipAddress) {
  try {
    db.prepare(`
      INSERT INTO audit_log (id, actor_id, action, resource_type, resource_id, details, ip_address, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      uuidv4(),
      actorId || 'system',
      action,
      resourceType || null,
      resourceId || null,
      details || null,
      ipAddress || null,
      Date.now()
    );
  } catch (err) {
    console.error('[AUDIT] Failed to write audit entry:', err.message);
  }
}

function getAuditLog(db, options = {}) {
  const { limit = 50, offset = 0, actorId, action } = options;

  let query = 'SELECT * FROM audit_log';
  const params = [];
  const conditions = [];

  if (actorId) {
    conditions.push('actor_id = ?');
    params.push(actorId);
  }
  if (action) {
    conditions.push('action = ?');
    params.push(action);
  }

  if (conditions.length > 0) {
    query += ' WHERE ' + conditions.join(' AND ');
  }

  query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?';
  params.push(limit, offset);

  return db.prepare(query).all(...params);
}

module.exports = { logAuditEvent, getAuditLog };