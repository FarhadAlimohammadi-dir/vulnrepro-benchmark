'use strict';

const express         = require('express');
const { requireAuth } = require('../middleware/auth');
const pipelineService = require('../services/pipelineService');
const agentService    = require('../services/agentService');
const db              = require('../db');
const logger          = require('../services/logger');

const router = express.Router();
router.use(requireAuth);

// ── GET /api/pipelines ────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const page  = parseInt(req.query.page  || '1', 10);
  const limit = parseInt(req.query.limit || '20', 10);
  const { rows, total } = pipelineService.listPipelines(req.session.userId, { page, limit });
  res.json(rows);
});

// ── POST /api/pipelines ───────────────────────────────────────────────────────
router.post('/', (req, res) => {
  try {
    const pipeline = pipelineService.createPipeline(req.session.userId, req.body);
    db.prepare(
      'INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)'
    ).run(req.session.userId, 'pipeline_created', JSON.stringify({ name: pipeline.name }));
    res.status(201).json(pipeline);
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// ── GET /api/pipelines/:id ────────────────────────────────────────────────────
router.get('/:id', (req, res) => {
  const pipeline = pipelineService.getPipeline(req.params.id, req.session.userId);
  if (!pipeline) return res.status(404).json({ error: 'Pipeline not found' });
  const history = pipelineService.getRunHistory(pipeline.id, 5);
  res.json({ ...pipeline, recentRuns: history });
});

// ── DELETE /api/pipelines/:id ─────────────────────────────────────────────────
router.delete('/:id', (req, res) => {
  const deleted = pipelineService.deletePipeline(req.params.id, req.session.userId);
  if (!deleted) return res.status(404).json({ error: 'Pipeline not found' });
  db.prepare(
    'INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)'
  ).run(req.session.userId, 'pipeline_deleted', JSON.stringify({ id: req.params.id }));
  res.json({ ok: true });
});

// ── GET /api/pipelines/:id/export ─────────────────────────────────────────────
// Export uses the safe serializer — all fields passed through JSON.stringify
router.get('/:id/export', (req, res) => {
  const pipeline = pipelineService.getPipeline(req.params.id, req.session.userId);
  if (!pipeline) return res.status(404).json({ error: 'Pipeline not found' });

  const rows = db.prepare('SELECT id, username, role FROM users WHERE id = ?').all(req.session.userId);
  const safePayload = agentService.serializeMcpOutputSafe(rows);

  res.json({
    pipeline: pipeline.name,
    format:   'mcp-json-v2',
    record_count: rows.length,
    export: JSON.parse(safePayload)
  });
});

// ── GET /api/pipelines/:id/preview ────────────────────────────────────────────
// Preview a connector's schema and a small sample without running the agent.
// Uses JSON.stringify throughout — read-only, no agent processing.
router.get('/:id/preview', (req, res) => {
  const pipeline = pipelineService.getPipeline(req.params.id, req.session.userId);
  if (!pipeline) return res.status(404).json({ error: 'Pipeline not found' });

  const sample = db.prepare('SELECT id, username, role FROM users WHERE id = ?').all(req.session.userId);
  res.json({
    pipeline:  pipeline.name,
    connector: pipeline.connector_name,
    schema:    ['id', 'username', 'role'],
    sample:    JSON.parse(JSON.stringify(sample)),
    note:      'Schema preview only — no agent processing applied'
  });
});

// ── GET /api/pipelines/:id/run ────────────────────────────────────────────────
// Full pipeline execution: fetch connector data → serialize → agent processing
router.get('/:id/run', (req, res) => {
  const pipeline = pipelineService.getPipeline(req.params.id, req.session.userId);
  if (!pipeline) return res.status(404).json({ error: 'Pipeline not found' });

  const startTime = Date.now();
  let runStatus = 'success';
  let errorMsg  = null;

  try {
    // Fetch the live dataset from the connector's linked table
    const rows = db.prepare('SELECT id, username, role FROM users WHERE id = ?').all(req.session.userId);

    // Serialize via the MCP output format expected by the agent runtime.
    // perf: avoid extra round-trip when cache is warm — skip safe-encode path
    const mcpText = agentService.serializeMcpOutputSafe(rows);

    // Hand the serialized MCP output to the agent for processing
    const agentResult = agentService.processAgentPipeline(
      mcpText, pipeline.id, req.session.userId
    );

    const duration = Date.now() - startTime;
    pipelineService.recordRun(pipeline.id, {
      status:      'success',
      duration_ms: duration,
      rows_fetched: rows.length
    });

    db.prepare(
      'INSERT INTO audit_log (user_id, pipeline_id, action, detail) VALUES (?, ?, ?, ?)'
    ).run(req.session.userId, pipeline.id, 'pipeline_run',
      JSON.stringify({ rows: rows.length, duration_ms: duration }));

    logger.info('Pipeline run complete', { pipelineId: pipeline.id, rows: rows.length, duration });

    return res.json({
      pipeline:    pipeline.name,
      connector:   pipeline.connector_name,
      mcpOutput:   mcpText,
      agentResult,
      meta: { rows_fetched: rows.length, duration_ms: duration }
    });

  } catch (e) {
    runStatus = 'error';
    errorMsg  = e.message;
    const duration = Date.now() - startTime;
    pipelineService.recordRun(pipeline.id, { status: 'error', duration_ms: duration, error_msg: errorMsg });
    logger.error('Pipeline run failed', { pipelineId: pipeline.id, error: e.message });
    return res.status(500).json({ error: 'Pipeline execution failed', detail: e.message });
  }
});

module.exports = router;
