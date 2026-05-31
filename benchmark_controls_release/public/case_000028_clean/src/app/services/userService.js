'use strict';

const { getDb } = require('../db');

function getUserById(id) {
  return getDb().prepare('SELECT id, username, role, api_token, email, display_name, bio, created_at, last_login FROM users WHERE id = ?').get(id);
}

function getUserByCredentials(username, password) {
  return getDb().prepare(
    'SELECT id, username, role, api_token FROM users WHERE username = ? AND password_hash = ?'
  ).get(username, password);
}

function listUsers() {
  return getDb().prepare(
    'SELECT id, username, role, email, display_name, created_at, last_login FROM users ORDER BY id ASC'
  ).all();
}

function updateProfile(id, { email, displayName, bio }) {
  getDb().prepare(
    'UPDATE users SET email = ?, display_name = ?, bio = ? WHERE id = ?'
  ).run(email, displayName, bio, id);
}

function updateLastLogin(id) {
  getDb().prepare("UPDATE users SET last_login = datetime('now') WHERE id = ?").run(id);
}

function setRole(id, role) {
  const allowed = ['viewer', 'operator', 'admin'];
  if (!allowed.includes(role)) throw new Error('Invalid role');
  getDb().prepare('UPDATE users SET role = ? WHERE id = ?').run(role, id);
}

module.exports = { getUserById, getUserByCredentials, listUsers, updateProfile, updateLastLogin, setRole };