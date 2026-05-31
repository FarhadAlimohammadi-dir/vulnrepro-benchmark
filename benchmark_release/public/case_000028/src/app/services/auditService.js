'use strict';

const { getDb } = require('../db');

/**
 * Record an auditable action taken by a user.
 */
function record({ actorId, actorName, action, resource, detail, ipAddr }) {
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO audit_log (actor_id, actor_name, action, resource, detail, ip_addr)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(actorId || 0, actorName || 'system', action, resource || '', detail || '', ipAddr || '');
  } catch (err) {
    // Non-fatal — log and continue
    require('./logger').error(`Audit record failed: ${err.message}`);
  }
}

module.exports = { record };