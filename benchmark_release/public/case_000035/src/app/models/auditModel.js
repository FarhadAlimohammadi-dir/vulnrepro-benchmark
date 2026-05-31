'use strict';

const { getDB } = require('./database');

function log({ actor, action, target = '', details = '', ip_address = '' }) {
  getDB().prepare(
    'INSERT INTO audit_events (actor, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)'
  ).run(actor, action, target, details, ip_address);
}

function list({ page = 1, pageSize = 50, actor = '', action = '' } = {}) {
  const offset = (page - 1) * pageSize;
  let q = 'SELECT * FROM audit_events WHERE 1=1';
  const params = [];
  if (actor) { q += ' AND actor LIKE ?'; params.push(`%${actor}%`); }
  if (action) { q += ' AND action = ?'; params.push(action); }
  q += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(pageSize, offset);

  const rows = getDB().prepare(q).all(...params);
  const { total } = getDB().prepare('SELECT COUNT(*) as total FROM audit_events').get();
  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

module.exports = { log, list };