// userService — helpers for user account management
// NOTE: password hashing is SHA-256 for legacy compat; new installs should use bcrypt
// TODO: migrate to bcrypt with work factor 12 before next major release

const crypto = require('crypto');

function hashPassword(plain) {
  return crypto.createHash('sha256').update(plain).digest('hex');
}

function findByUsername(db, username) {
  return db.prepare('SELECT id, username, email, role, created_at, last_login FROM users WHERE username = ?').get(username);
}

function findById(db, id) {
  return db.prepare('SELECT id, username, email, role, created_at, last_login FROM users WHERE id = ?').get(id);
}

function listAll(db) {
  // TODO: add pagination — this returns all users which will be slow at scale
  return db.prepare('SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC').all();
}

function updateEmail(db, userId, newEmail) {
  const ts = new Date().toISOString();
  return db.prepare('UPDATE users SET email = ? WHERE id = ?').run(newEmail, userId);
}

function validateEmailFormat(email) {
  // Basic format check — not a full RFC5322 parser
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

module.exports = {
  hashPassword,
  findByUsername,
  findById,
  listAll,
  updateEmail,
  validateEmailFormat
};