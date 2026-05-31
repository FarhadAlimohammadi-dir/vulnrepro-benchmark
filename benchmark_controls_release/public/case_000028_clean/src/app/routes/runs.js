'use strict';

const express = require('express');
const router = express.Router();
const runService = require('../services/runService');
const { record } = require('../services/auditService');

// List runs with filtering + pagination
router.get('/', (req, res) => {
  const page     = Math.max(1, parseInt(req.query.page, 10) || 1);
  const status   = req.query.status || '';
  const model    = req.query.model  || '';
  const pageSize = 10;

  const result = runService.listRuns({ page, pageSize, status: status || undefined, model: model || undefined });

  res.render('runs_list', {
    ...result,
    filterStatus: status,
    filterModel:  model,
    user: req.session.username,
    role: req.session.role
  });
});

// Create new run
router.post('/', (req, res) => {
  const { model_name, config_json, notes } = req.body;
  if (!model_name || typeof model_name !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(model_name.trim())) {
    req.session.flash = 'Invalid model name.';
    return res.redirect('/runs');
  }
  let parsedConfig = '{}';
  try {
    parsedConfig = JSON.stringify(JSON.parse(config_json || '{}'));
  } catch {
    parsedConfig = '{}';
  }
  const newId = runService.createRun({
    modelName:  model_name.trim(),
    configJson: parsedConfig,
    notes:      (notes || '').slice(0, 500),
    ownerId:    req.session.userId
  });
  record({ actorId: req.session.userId, actorName: req.session.username, action: 'CREATE_RUN', resource: `training_runs/${newId}`, detail: `Model: ${model_name.trim()}`, ipAddr: req.ip });
  res.redirect(`/runs/${newId}`);
});

// Run detail
router.get('/:id', (req, res) => {
  const runId = parseInt(req.params.id, 10);
  if (isNaN(runId)) return res.status(400).render('error', { code: 400, message: 'Invalid run ID' });
  const run = runService.getRunById(runId);
  if (!run) return res.status(404).render('error', { code: 404, message: 'Run not found' });

  const { getDb } = require('../db');
  const db = getDb();
  const metrics = db.prepare('SELECT metric_name, metric_value, recorded_at FROM metrics WHERE run_id = ? ORDER BY recorded_at ASC').all(runId);

  res.render('run_detail', {
    run,
    metrics,
    user: req.session.username,
    role: req.session.role
  });
});

// Update notes
router.post('/:id/notes', (req, res) => {
  const runId = parseInt(req.params.id, 10);
  if (isNaN(runId)) return res.status(400).render('error', { code: 400, message: 'Invalid run ID' });
  const notes = (req.body.notes || '').slice(0, 500);
  runService.updateRunNotes(runId, notes, req.session.userId);
  record({ actorId: req.session.userId, actorName: req.session.username, action: 'UPDATE_RUN', resource: `training_runs/${runId}`, detail: 'Notes updated', ipAddr: req.ip });
  res.redirect(`/runs/${runId}`);
});

// Cancel run (operator+ AND owner, or admin)
router.post('/:id/cancel', (req, res) => {
  if (!['operator','admin'].includes(req.session.role)) {
    return res.status(403).render('error', { code: 403, message: 'Not authorized' });
  }
  const runId = parseInt(req.params.id, 10);
  if (isNaN(runId)) return res.status(400).render('error', { code: 400, message: 'Invalid run ID' });
  const run = runService.getRunById(runId);
  if (!run) return res.status(404).render('error', { code: 404, message: 'Run not found' });
  if (req.session.role !== 'admin' && run.owner_id !== req.session.userId) {
    return res.status(403).render('error', { code: 403, message: 'Not authorized' });
  }
  runService.cancelRun(runId, req.session.userId, req.session.role);
  record({ actorId: req.session.userId, actorName: req.session.username, action: 'CANCEL_RUN', resource: `training_runs/${runId}`, detail: 'Run cancelled', ipAddr: req.ip });
  res.redirect(`/runs/${runId}`);
});

module.exports = router;