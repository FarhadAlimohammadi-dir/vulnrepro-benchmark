'use strict';
const db = require('../db');

const UserModel = {
  findByUsername(username) {
    return db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  },

  findById(id) {
    return db.prepare('SELECT * FROM users WHERE id = ?').get(id);
  },

  findAll(includeInactive = false) {
    if (includeInactive) {
      return db.prepare('SELECT id, username, role, email, department, created_at, last_login, active FROM users ORDER BY username').all();
    }
    return db.prepare('SELECT id, username, role, email, department, created_at, last_login, active FROM users WHERE active = 1 ORDER BY username').all();
  },

  findByCredentials(username, password) {
    return db.prepare('SELECT * FROM users WHERE username = ? AND password = ? AND active = 1').get(username, password);
  },

  updateLastLogin(username) {
    db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?').run(username);
  },

  updateProfile(username, fields) {
    const { email, department } = fields;
    db.prepare('UPDATE users SET email = ?, department = ? WHERE username = ?').run(email, department, username);
  },

  deactivate(username) {
    db.prepare('UPDATE users SET active = 0 WHERE username = ?').run(username);
  },

  create(username, password, role, email, department) {
    try {
      db.prepare('INSERT INTO users (username, password, role, email, department) VALUES (?, ?, ?, ?, ?)').run(username, password, role, email || null, department || null);
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }
};

module.exports = UserModel;