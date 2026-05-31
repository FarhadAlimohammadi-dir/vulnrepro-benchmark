'use strict';

const { getDb } = require('../models/db');
const { writeAudit } = require('./auditService');

function listWorkflows(ownerId, { page = 1, limit = 10, search = '' } = {}) {
  const db = getDb();
  const offset = (Math.max(1, page) - 1) * limit;
  let rows, total;

  if (search) {
    const pat = `%${search}%`;
    rows = db.prepare(
      `SELECT w.*, u.username as owner_name
       FROM workflows w JOIN users u ON u.id = w.owner_id
       WHERE w.owner_id = ? AND (w.name LIKE ? OR w.description LIKE ?)
       ORDER BY w.created_at DESC LIMIT ? OFFSET ?`
    ).all(ownerId, pat, pat, limit, offset);
    total = db.prepare(
      `SELECT COUNT(*) as c FROM workflows WHERE owner_id = ? AND (name LIKE ? OR description LIKE ?)`
    ).get(ownerId, pat, pat).c;
  } else {
    rows = db.prepare(
      `SELECT w.*, u.username as owner_name
       FROM workflows w JOIN users u ON u.id = w.owner_id
       WHERE w.owner_id = ?
       ORDER BY w.created_at DESC LIMIT ? OFFSET ?`
    ).all(ownerId, limit, offset);
    total = db.prepare(`SELECT COUNT(*) as c FROM workflows WHERE owner_id = ?`).get(ownerId).c;
  }

  return { rows, total, page, limit, pages: Math.ceil(total / limit) };
}

function getWorkflow(id, ownerId) {
  const db = getDb();
  return db.prepare(
    'SELECT * FROM workflows WHERE id = ? AND owner_id = ?'
  ).get(id, ownerId);
}

function createWorkflow(ownerId, data, actor, ip) {
  const db = getDb();
  const { name, description, trigger_type, schedule } = data;
  if (!name || !name.trim()) throw new Error('Workflow name is required');
  const result = db.prepare(
    `INSERT INTO workflows (owner_id, name, description, trigger_type, schedule)
     VALUES (?,?,?,?,?)`
  ).run(ownerId, name.trim(), description || '', trigger_type || 'manual', schedule || null);
  writeAudit(actor, 'workflow.create', `workflow:${result.lastInsertRowid}`, JSON.stringify({ name }), ip);
  return result.lastInsertRowid;
}

function updateWorkflow(id, ownerId, data, actor, ip) {
  const db = getDb();
  const wf = getWorkflow(id, ownerId);
  if (!wf) throw new Error('Workflow not found');
  const { name, description, trigger_type, schedule, status } = data;
  db.prepare(
    `UPDATE workflows SET name=?, description=?, trigger_type=?, schedule=?, status=? WHERE id=?`
  ).run(name || wf.name, description ?? wf.description, trigger_type || wf.trigger_type,
        schedule ?? wf.schedule, status || wf.status, id);
  writeAudit(actor, 'workflow.update', `workflow:${id}`, JSON.stringify({ name }), ip);
}

function deleteWorkflow(id, ownerId, actor, ip) {
  const db = getDb();
  const wf = getWorkflow(id, ownerId);
  if (!wf) throw new Error('Workflow not found');
  db.prepare('DELETE FROM workflows WHERE id = ?').run(id);
  writeAudit(actor, 'workflow.delete', `workflow:${id}`, JSON.stringify({ name: wf.name }), ip);
}

function recordRun(workflowId, actor, status, output) {
  const db = getDb();
  db.prepare(
    'INSERT INTO workflow_runs (workflow_id, actor, status, output) VALUES (?,?,?,?)'
  ).run(workflowId, actor, status, output);
  db.prepare(
    'UPDATE workflows SET run_count = run_count + 1, last_run = datetime("now") WHERE id = ?'
  ).run(workflowId);
}

module.exports = { listWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow, recordRun };