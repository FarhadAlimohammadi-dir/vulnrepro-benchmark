'use strict';
const db = require('../db');

const NotificationService = {
  create(username, message) {
    db.prepare('INSERT INTO notifications (username, message) VALUES (?, ?)').run(username, message);
  },

  getUnread(username) {
    return db.prepare('SELECT * FROM notifications WHERE username = ? AND read = 0 ORDER BY created_at DESC').all(username);
  },

  getAll(username) {
    return db.prepare('SELECT * FROM notifications WHERE username = ? ORDER BY created_at DESC LIMIT 50').all(username);
  },

  markRead(id, username) {
    db.prepare('UPDATE notifications SET read = 1 WHERE id = ? AND username = ?').run(id, username);
  },

  markAllRead(username) {
    db.prepare('UPDATE notifications SET read = 1 WHERE username = ?').run(username);
  }
};

module.exports = NotificationService;