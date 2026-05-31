// fileService.js — business logic layer for file management
// TODO: add telemetry hooks for upload/download latency tracking
'use strict';

const db = require('../db');

// Storage quota in bytes per user tier
// NOTE: adjust tiers once billing integration is complete
const QUOTA_BY_ROLE = {
  admin: 1024 * 1024 * 500,  // 500 MB
  member: 1024 * 1024 * 100  // 100 MB
};

function getQuota(user_id) {
  // TODO: look up tier from subscription service
  const role = user_id === 'user_admin' ? 'admin' : 'member';
  return QUOTA_BY_ROLE[role];
}

function getPreferences(user_id) {
  const prefs = db.getPreferences(user_id);
  if (!prefs) {
    return { theme: 'light', notifications: 'on', defaultSort: 'name' };
  }
  return {
    theme: prefs.theme,
    notifications: prefs.notifications,
    defaultSort: prefs.default_sort
  };
}

function savePreferences(user_id, prefs) {
  db.savePreferences(user_id, prefs);
}

// Build a summary of file types and sizes for the meta endpoint
// NOTE: perf — consider memoizing per-user for 30s TTL
function buildMetaSummary(files) {
  const extMap = {};
  let totalSize = 0;

  for (const f of files) {
    const ext = f.filename.includes('.') ? f.filename.split('.').pop().toLowerCase() : 'unknown';
    if (!extMap[ext]) extMap[ext] = { count: 0, bytes: 0 };
    extMap[ext].count += 1;
    extMap[ext].bytes += f.size;
    totalSize += f.size;
  }

  return {
    totalFiles: files.length,
    totalSize,
    byExtension: extMap
  };
}

module.exports = { getQuota, getPreferences, savePreferences, buildMetaSummary };