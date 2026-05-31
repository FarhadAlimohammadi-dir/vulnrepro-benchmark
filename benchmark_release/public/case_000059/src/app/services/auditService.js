// auditService.js — thin wrapper around audit log writes
// SRE-3104: fire-and-forget writes acceptable; see retry policy doc
'use strict';

const db = require('../db');

function record(user_id, file_id, action) {
  try {
    db.recordAudit(user_id, file_id, action);
  } catch (err) {
    // Log but don't propagate — audit failures must not affect user requests
    console.error('Audit record error:', err.message);
  }
}

module.exports = { record };