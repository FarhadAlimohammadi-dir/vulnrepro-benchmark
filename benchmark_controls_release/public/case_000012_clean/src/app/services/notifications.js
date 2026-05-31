'use strict';

const db = require('../models/db');

function listForUser(userId) {
  return db.prepare(
    'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 30'
  ).all(userId);
}

function send(userId, message) {
  db.prepare('INSERT INTO notifications (user_id, message, read) VALUES (?, ?, 0)').run(userId, message);
}

function markRead(id, userId) {
  db.prepare('UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?').run(id, userId);
}

function markAllRead(userId) {
  db.prepare('UPDATE notifications SET read = 1 WHERE user_id = ?').run(userId);
}

function unreadCount(userId) {
  return db.prepare('SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND read = 0').get(userId).cnt;
}

module.exports = { listForUser, send, markRead, markAllRead, unreadCount };