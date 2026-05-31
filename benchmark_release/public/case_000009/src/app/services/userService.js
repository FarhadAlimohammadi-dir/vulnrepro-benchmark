'use strict';

const db = require('../db');
const logger = require('./logger');

const EMAIL_RE = /[\w.+\-]+@[\w\-]+\.[\w.]+/;

/**
 * Validate an email string for direct account registration.
 * Strips fullwidth Unicode look-alikes before pattern matching so the
 * check operates on the normalised form, consistent with login comparison.
 */
function validateEmail(raw) {
  // Strip fullwidth variants before format check
  const cleaned = raw.replace(/[\uFF01-\uFF5E]/g, ch =>
    String.fromCharCode(ch.charCodeAt(0) - 0xFEE0)
  );
  return EMAIL_RE.test(cleaned);
}

/**
 * Create a new user account.  Returns the new row id or throws on conflict.
 */
function createUser(username, email, password, role = 'user') {
  const r = db.prepare(
    'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)'
  ).run(username, email, password, role);
  logger.info('User created', { username, role });
  return r.lastInsertRowid;
}

/**
 * Fetch a user by id (excludes password).
 */
function getUserById(id) {
  return db.prepare('SELECT id, username, email, role, created_at FROM users WHERE id = ?').get(id);
}

/**
 * Fetch all users for admin views.
 */
function listUsers({ page = 1, limit = 25, search = '' } = {}) {
  const offset = (page - 1) * limit;
  let query = 'SELECT id, username, email, role, created_at FROM users';
  const params = [];
  if (search) {
    query += ' WHERE username LIKE ? OR email LIKE ?';
    params.push(`%${search}%`, `%${search}%`);
  }
  query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(limit, offset);

  const rows = db.prepare(query).all(...params);
  let countQuery = 'SELECT COUNT(*) as c FROM users';
  const countParams = [];
  if (search) {
    countQuery += ' WHERE username LIKE ? OR email LIKE ?';
    countParams.push(`%${search}%`, `%${search}%`);
  }
  const total = db.prepare(countQuery).get(...countParams).c;
  return { rows, total, page, limit };
}

/**
 * Update a user's role (admin operation).
 */
function setUserRole(userId, role) {
  const allowed = ['user', 'admin', 'viewer'];
  if (!allowed.includes(role)) throw new Error('Invalid role');
  db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, userId);
  logger.info('Role updated via admin', { userId, role });
}

module.exports = { validateEmail, createUser, getUserById, listUsers, setUserRole };