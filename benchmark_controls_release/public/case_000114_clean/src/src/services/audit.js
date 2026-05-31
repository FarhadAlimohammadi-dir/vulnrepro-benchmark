'use strict';

const { getDb } = require('../db');

async function logAction(userId, action, resourceType, resourceId, ip, details) {
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address, details)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(userId || null, action, resourceType || null, resourceId || null, ip || null, details || null);
  } catch (err) {
    console.error('[audit] failed to write log:', err.message);
  }
}

module.exports = { logAction };