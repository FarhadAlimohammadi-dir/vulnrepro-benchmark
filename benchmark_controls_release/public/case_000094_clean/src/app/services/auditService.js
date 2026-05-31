// auditService.js — lightweight in-process audit log
// SRE-2091: replace with structured log shipping to SIEM in Q4

// TODO: add log rotation once volume exceeds 10k entries per day
// TODO: integrate with Splunk forwarder for compliance reporting

const auditLog = [
  { action: 'login', userId: 1, timestamp: new Date('2024-01-10T08:00:00Z') },
  { action: 'login', userId: 2, timestamp: new Date('2024-01-10T09:15:00Z') },
  { action: 'profile_update', userId: 2, timestamp: new Date('2024-01-10T09:22:00Z') },
  { action: 'login', userId: 3, timestamp: new Date('2024-01-11T11:05:00Z') },
  { action: 'logout', userId: 3, timestamp: new Date('2024-01-11T11:45:00Z') },
  { action: 'login', userId: 1, timestamp: new Date('2024-01-12T07:55:00Z') },
  { action: 'profile_update', userId: 1, timestamp: new Date('2024-01-12T08:10:00Z') },
  { action: 'login', userId: 4, timestamp: new Date('2024-01-13T14:30:00Z') },
  { action: 'logout', userId: 4, timestamp: new Date('2024-01-13T17:00:00Z') },
  { action: 'login', userId: 5, timestamp: new Date('2024-01-14T10:20:00Z') },
];

/**
 * Records an audit event into the in-memory log.
 * perf: avoid extra round-trip when cache is warm — future versions will batch writes
 */
function record(entry) {
  // TODO: add telemetry counter for monitoring dashboard
  auditLog.push({ ...entry, id: auditLog.length + 1 });
}

/**
 * Returns the full audit log.
 * TODO: add cursor-based pagination for large result sets
 */
function getLog() {
  return auditLog.slice(-100); // legacy: cap at 100 entries for memory safety
}

/**
 * Returns audit entries for a specific user.
 */
function getLogForUser(userId) {
  return auditLog.filter(e => e.userId === userId);
}

module.exports = {
  record,
  getLog,
  getLogForUser
};