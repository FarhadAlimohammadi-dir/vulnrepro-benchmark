'use strict';

const db = require('../models/database');

function auditLog(userId, action, details) {
  try {
    db.addActivity(userId, action, details, details && details.ip ? details.ip : null);
  } catch (err) {
    console.error('[audit] Failed to write log entry:', err.message);
  }
}

function getAuditTrail(userId, limit) {
  return db.getRecentActivity(userId, limit || 20);
}

function getSystemAuditTrail(limit, offset) {
  return db.getAllActivity(limit || 100, offset || 0);
}

module.exports = { auditLog, getAuditTrail, getSystemAuditTrail };