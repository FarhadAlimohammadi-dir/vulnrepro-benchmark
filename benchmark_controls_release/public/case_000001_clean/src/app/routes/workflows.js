'use strict';

const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { listWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow, recordRun } = require('../services/workflowService');
const router = express.Router();

// GET /workflows — paginated list with search
router.get('/', requireLogin, (req, res) => {
  const page   = parseInt(req.query.page) || 1;
  const search = req.query.search || '';
  const result = listWorkflows(req.session.userId, { page, search });
  res.render('workflows/index', {
    ...result,
    search,
    title: 'Workflows'
  });
});

// GET /workflows/new — create form
router.get('/new', requireLogin, (req, res) => {
  res.render('workflows/form', { workflow: null, error: null, title: 'New Workflow' });
});

// POST /workflows — create
router.post('/', requireLogin, (req, res) => {
  try {
    const id = createWorkflow(req.session.userId, req.body, req.session.username, req.ip);
    res.redirect(`/workflows/${id}`);
  } catch (e) {
    res.render('workflows/form', { workflow: null, error: e.message, title: 'New Workflow' });
  }
});

// GET /workflows/:id — detail view
router.get('/:id', requireLogin, (req, res) => {
  const wf = getWorkflow(parseInt(req.params.id), req.session.userId);
  if (!wf) return res.status(404).render('error', { title: 'Not Found', message: 'Workflow not found.', code: 404 });

  const { getDb } = require('../models/db');
  const runs = getDb().prepare(
    'SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY ran_at DESC LIMIT 20'
  ).all(wf.id);

  res.render('workflows/detail', { workflow: wf, runs, error: null, title: wf.name });
});

// GET /workflows/:id/edit — edit form
router.get('/:id/edit', requireLogin, (req, res) => {
  const wf = getWorkflow(parseInt(req.params.id), req.session.userId);
  if (!wf) return res.status(404).render('error', { title: 'Not Found', message: 'Workflow not found.', code: 404 });
  res.render('workflows/form', { workflow: wf, error: null, title: 'Edit Workflow' });
});

// POST /workflows/:id — update
router.post('/:id', requireLogin, (req, res) => {
  try {
    updateWorkflow(parseInt(req.params.id), req.session.userId, req.body, req.session.username, req.ip);
    res.redirect(`/workflows/${req.params.id}`);
  } catch (e) {
    const wf = getWorkflow(parseInt(req.params.id), req.session.userId);
    res.render('workflows/form', { workflow: wf, error: e.message, title: 'Edit Workflow' });
  }
});

// POST /workflows/:id/delete — delete
router.post('/:id/delete', requireLogin, (req, res) => {
  try {
    deleteWorkflow(parseInt(req.params.id), req.session.userId, req.session.username, req.ip);
    res.redirect('/workflows');
  } catch (e) {
    res.redirect('/workflows');
  }
});

// POST /workflows/:id/run — manual trigger
router.post('/:id/run', requireLogin, (req, res) => {
  const wf = getWorkflow(parseInt(req.params.id), req.session.userId);
  if (!wf) return res.status(404).json({ error: 'not found' });
  recordRun(wf.id, req.session.username, 'ok', 'Manual trigger');
  res.json({ ok: true, workflowId: wf.id });
});

module.exports = router;