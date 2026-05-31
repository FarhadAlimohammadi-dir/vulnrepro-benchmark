'use strict';

const { getDb } = require('../db');

function listRuns({ page = 1, pageSize = 15, status, model, ownerId } = {}) {
  const db = getDb();
  const offset = (page - 1) * pageSize;
  const conditions = [];
  const params = [];

  if (status && ['pending', 'running', 'completed', 'failed'].includes(status)) {
    conditions.push('status = ?');
    params.push(status);
  }
  if (model && typeof model === 'string' && /^[a-zA-Z0-9_-]+$/.test(model)) {
    conditions.push('model_name = ?');
    params.push(model);
  }
  if (ownerId) {
    conditions.push('owner_id = ?');
    params.push(ownerId);
  }

  const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
  const rows = db.prepare(
    `SELECT id, model_name, status, notes, owner_id, started_at, finished_at
     FROM training_runs ${where}
     ORDER BY started_at DESC
     LIMIT ? OFFSET ?`
  ).all(...params, pageSize, offset);

  const total = db.prepare(
    `SELECT COUNT(*) as c FROM training_runs ${where}`
  ).get(...params).c;

  return { rows, total, page, pageSize, totalPages: Math.ceil(total / pageSize) };
}

function getRunById(id) {
  return getDb().prepare('SELECT * FROM training_runs WHERE id = ?').get(id);
}

function createRun({ modelName, configJson, notes, ownerId }) {
  const db = getDb();
  const result = db.prepare(`
    INSERT INTO training_runs (model_name, status, config_json, notes, owner_id)
    VALUES (?, 'pending', ?, ?, ?)
  `).run(modelName, configJson || '{}', notes || '', ownerId);
  return result.lastInsertRowid;
}

function updateRunNotes(id, notes, ownerId) {
  const db = getDb();
  db.prepare('UPDATE training_runs SET notes = ? WHERE id = ? AND owner_id = ?')
    .run(notes, id, ownerId);
}

function cancelRun(id, ownerId, role) {
  const db = getDb();
  if (role === 'admin') {
    db.prepare("UPDATE training_runs SET status = 'failed', finished_at = datetime('now') WHERE id = ? AND status IN ('pending','running')")
      .run(id);
  } else {
    db.prepare("UPDATE training_runs SET status = 'failed', finished_at = datetime('now') WHERE id = ? AND owner_id = ? AND status IN ('pending','running')")
      .run(id, ownerId);
  }
}

module.exports = { listRuns, getRunById, createRun, updateRunNotes, cancelRun };