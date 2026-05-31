'use strict';

const { db } = require('../db');

function listContacts(userId, { page = 1, perPage = 20, search = '' } = {}) {
  const offset = (page - 1) * perPage;
  if (search) {
    const q = `%${search}%`;
    const rows  = db.prepare('SELECT * FROM contacts WHERE user_id=? AND (name LIKE ? OR phone LIKE ? OR email LIKE ?) ORDER BY name LIMIT ? OFFSET ?').all(userId, q, q, q, perPage, offset);
    const total = db.prepare('SELECT COUNT(*) as c FROM contacts WHERE user_id=? AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)').get(userId, q, q, q).c;
    return { rows, total, page, perPage };
  }
  const rows  = db.prepare('SELECT * FROM contacts WHERE user_id=? ORDER BY name LIMIT ? OFFSET ?').all(userId, perPage, offset);
  const total = db.prepare('SELECT COUNT(*) as c FROM contacts WHERE user_id=?').get(userId).c;
  return { rows, total, page, perPage };
}

function getContact(userId, id) {
  return db.prepare('SELECT * FROM contacts WHERE user_id=? AND id=?').get(userId, id);
}

function createContact(userId, { name, phone, email, notes }) {
  if (!name || name.length > 120) throw new Error('Invalid contact name');
  const row = db.prepare('INSERT INTO contacts (user_id,name,phone,email,notes) VALUES (?,?,?,?,?)').run(
    userId, name.slice(0,120), (phone||'').slice(0,30), (email||'').slice(0,100), (notes||'').slice(0,500)
  );
  return row.lastInsertRowid;
}

function updateContact(userId, id, { name, phone, email, notes }) {
  if (!name || name.length > 120) throw new Error('Invalid contact name');
  db.prepare('UPDATE contacts SET name=?,phone=?,email=?,notes=? WHERE user_id=? AND id=?').run(
    name.slice(0,120), (phone||'').slice(0,30), (email||'').slice(0,100), (notes||'').slice(0,500), userId, id
  );
}

function deleteContact(userId, id) {
  db.prepare('DELETE FROM contacts WHERE user_id=? AND id=?').run(userId, id);
}

module.exports = { listContacts, getContact, createContact, updateContact, deleteContact };