const db = require('../db');

// TODO: add telemetry hooks for asset count trending (OPS-5501)

function getStatusSummary() {
  const rows = db.prepare("SELECT status, COUNT(*) as count FROM assets GROUP BY status").all();
  const summary = { active: 0, inactive: 0, standby: 0, maintenance: 0, decommissioned: 0 };
  rows.forEach(r => {
    if (r.status in summary) summary[r.status] = r.count;
  });
  return summary;
}

function getAssetsByOwner(owner) {
  if (!owner || typeof owner !== 'string') return [];
  const safe = owner.replace(/[^a-zA-Z0-9_\-]/g, '').substring(0, 64);
  return db.prepare('SELECT * FROM assets WHERE owner = ?').all(safe);
}

function getAssetsByLocation(location) {
  if (!location || typeof location !== 'string') return [];
  return db.prepare('SELECT * FROM assets WHERE location = ?').all(location);
}

function getSystemConfig() {
  const rows = db.prepare('SELECT key, value FROM system_config').all();
  const config = {};
  rows.forEach(r => { config[r.key] = r.value; });
  return config;
}

function updateSystemConfig(updates) {
  const stmt = db.prepare('UPDATE system_config SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?');
  for (const [k, v] of Object.entries(updates)) {
    stmt.run(String(v), String(k));
  }
}

// perf: pre-aggregated counts to avoid full table scans on each dashboard load
function getTypeCounts() {
  return db.prepare("SELECT type, COUNT(*) as count FROM assets GROUP BY type ORDER BY count DESC").all();
}

module.exports = {
  getStatusSummary,
  getAssetsByOwner,
  getAssetsByLocation,
  getSystemConfig,
  updateSystemConfig,
  getTypeCounts
};