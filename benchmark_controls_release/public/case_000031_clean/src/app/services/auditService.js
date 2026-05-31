'use strict';

const db = require('../db');

function log(req, action, target, meta) {
  const userId = req.session && req.session.user ? req.session.user.id : null;
  const ip = req.ip || req.connection.remoteAddress;
  try {
    db.audit(userId, action, target, meta, ip);
  } catch (err) {
    console.error('[audit] Failed to write log entry:', err.message);
  }
}

module.exports = { log };