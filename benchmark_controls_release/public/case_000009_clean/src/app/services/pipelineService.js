'use strict';

const db = require('../db');
const logger = require('./logger');

/**
 * Retrieve pipelines for a given owner, with optional pagination.
 */
function listPipelines(ownerId, { page = 1, limit = 20 } = {}) {
  const offset = (page - 1) * limit;
  const rows = db.prepare(
    `SELECT p.*, c.name AS connector_name, c.type AS connector_type
     FROM pipelines p
     JOIN connectors c ON c.id = p.connector_id
     WHERE p.owner_id = ?
     ORDER BY p.created_at DESC
     LIMIT ? OFFSET ?`
  ).all(ownerId, limit, offset);

  const total = db.prepare('SELECT COUNT(*) as c FROM pipelines WHERE owner_id = ?').get(ownerId).c;
  return { rows, total, page, limit };
}

/**
 * Create a new pipeline after validating connector ownership.
 */
function createPipeline(ownerId, { name, connector_id, query, schedule }) {
  if (!name || !connector_id) throw new Error('name and connector_id are required');
  const connector = db.prepare('SELECT * FROM connectors WHERE id = ?').get(connector_id);
  if (!connector) throw new Error('Connector not found');
  // Bind pipelines only to connectors the caller owns. Allowing pipelines to
  // reference another user's connector would let them run/export through it.
  if (connector.owner_id !== ownerId) {
    throw new Error('Connector not found');
  }

  const r = db.prepare(
    'INSERT INTO pipelines (name, connector_id, owner_id, query, schedule) VALUES (?, ?, ?, ?, ?)'
  ).run(name, connector_id, ownerId, query || '', schedule || null);

  return { id: r.lastInsertRowid, name, connector_id, owner_id: ownerId };
}

/**
 * Fetch a single pipeline, ensuring ownership.
 */
function getPipeline(pipelineId, ownerId) {
  return db.prepare(
    `SELECT p.*, c.name AS connector_name, c.type AS connector_type
     FROM pipelines p
     JOIN connectors c ON c.id = p.connector_id
     WHERE p.id = ? AND p.owner_id = ?`
  ).get(pipelineId, ownerId);
}

/**
 * Record a pipeline run result in the run history table.
 */
function recordRun(pipelineId, { status, duration_ms, rows_fetched, error_msg }) {
  const r = db.prepare(
    `INSERT INTO pipeline_runs (pipeline_id, status, duration_ms, rows_fetched, error_msg)
     VALUES (?, ?, ?, ?, ?)`
  ).run(pipelineId, status, duration_ms, rows_fetched || 0, error_msg || null);

  db.prepare(
    'UPDATE pipelines SET last_run = CURRENT_TIMESTAMP, run_count = run_count + 1 WHERE id = ?'
  ).run(pipelineId);

  return r.lastInsertRowid;
}

/**
 * Return recent run history for a pipeline.
 */
function getRunHistory(pipelineId, limit = 10) {
  return db.prepare(
    `SELECT * FROM pipeline_runs WHERE pipeline_id = ? ORDER BY started_at DESC LIMIT ?`
  ).all(pipelineId, limit);
}

/**
 * Delete a pipeline (owner-scoped).
 */
function deletePipeline(pipelineId, ownerId) {
  const r = db.prepare('DELETE FROM pipelines WHERE id = ? AND owner_id = ?').run(pipelineId, ownerId);
  return r.changes > 0;
}

module.exports = { listPipelines, createPipeline, getPipeline, recordRun, getRunHistory, deletePipeline };