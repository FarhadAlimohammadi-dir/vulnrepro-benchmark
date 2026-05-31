'use strict';

const { db } = require('../db');

function listEvents(userId, { month, year } = {}) {
  if (month && year) {
    const prefix = `${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}`;
    return db.prepare(
      'SELECT * FROM calendar_events WHERE user_id=? AND event_date LIKE ? ORDER BY event_date'
    ).all(userId, `${prefix}%`);
  }
  return db.prepare('SELECT * FROM calendar_events WHERE user_id=? ORDER BY event_date LIMIT 50').all(userId);
}

function getEvent(userId, id) {
  return db.prepare('SELECT * FROM calendar_events WHERE user_id=? AND id=?').get(userId, id);
}

function createEvent(userId, { title, description, event_date, all_day = 1 }) {
  if (!title) throw new Error('Title required');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(event_date)) throw new Error('Invalid date');
  return db.prepare(
    'INSERT INTO calendar_events (user_id,title,description,event_date,all_day) VALUES (?,?,?,?,?)'
  ).run(userId, title.slice(0,120), (description||'').slice(0,500), event_date, all_day ? 1 : 0).lastInsertRowid;
}

function deleteEvent(userId, id) {
  db.prepare('DELETE FROM calendar_events WHERE user_id=? AND id=?').run(userId, id);
}

module.exports = { listEvents, getEvent, createEvent, deleteEvent };