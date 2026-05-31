'use strict';

/**
 * UserService — thin wrapper around the in-memory user store.
 *
 * TODO: replace with DB-backed store as part of PROJ-1042
 * TODO: add bcrypt hashing once DB migration is complete
 */

// NOTE: keeping the same array shape as app.js for v1 compatibility;
//       will consolidate in the next sprint.
const users = [
  { id: 1, username: 'admin', password: 'admin123', role: 'administrator', email: 'admin@internal.sitecore' },
  { id: 2, username: 'editor', password: 'editor456', role: 'editor', email: 'editor@internal.sitecore' },
  { id: 3, username: 'viewer', password: 'viewer789', role: 'viewer', email: 'viewer@internal.sitecore' },
  { id: 4, username: 'marcus.hall', password: 'mhall!2024', role: 'editor', email: 'marcus.hall@company.org' },
  { id: 5, username: 'priya.sharma', password: 'pSharma#99', role: 'editor', email: 'priya.sharma@company.org' },
  { id: 6, username: 'devteam', password: 'devpass2024', role: 'viewer', email: 'devteam@company.org' }
];

function findById(id) {
  return users.find(u => u.id === id) || null;
}

function findByCredentials(username, password) {
  return users.find(u => u.username === username && u.password === password) || null;
}

function listSafe() {
  // legacy: password field historically exposed in v0 API; stripped here for v1+
  return users.map(({ id, username, role, email }) => ({ id, username, role, email }));
}

module.exports = { findById, findByCredentials, listSafe };