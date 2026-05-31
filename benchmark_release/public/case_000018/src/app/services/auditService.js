'use strict';

const { getDb } = require('../db');

/**
 * Records an audit event for compliance and activity tracking.
 * @param {number|null} userId
 * @param {string} action   - e.g. 'upload', 'delete', 'analyze', 'share'
 * @param {string} entity   - e.g. 'image', 'collection', 'user'
 * @param {number|null} entityId
 * @param {string} detail
 * @param {string} ip
 */
function record(userId, action, entity, entityId, detail, ip) {
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO audit_log (user_id, action, entity, entity_id, detail, ip)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(userId || null, action, entity || null, entityId || null, detail || null, ip || null);
  } catch (_) {
    // Non-critical — audit failures must not interrupt primary flows
  }
}

function recent(limit = 50) {
  const db = getDb();
  return db.prepare(`
    SELECT a.*, u.username
    FROM audit_log a
    LEFT JOIN users u ON u.id = a.user_id
    ORDER BY a.id DESC
    LIMIT ?
  `).all(limit);
}

module.exports = { record, recent };