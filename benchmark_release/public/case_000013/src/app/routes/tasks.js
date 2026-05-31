'use strict';

const express = require('express');
const router  = express.Router();
const taskSvc = require('../services/taskService');
const audit   = require('../services/auditService');

// POST /api/tasks/run
// Executes an approved workspace command on behalf of the authenticated user.
router.post('/run', (req, res) => {
  const { command, project_id } = req.body;

  if (!command || typeof command !== 'string' || command.length > 512) {
    return res.status(400).json({ error: 'command must be a non-empty string (max 512 chars)' });
  }
  if (!project_id) {
    return res.status(400).json({ error: 'project_id is required' });
  }

  const result = taskSvc.runWorkspaceCommand(command.trim(), project_id, req.session.userId);

  if (result.error) {
    const status = result.error.includes('denied') ? 403 : 400;
    return res.status(status).json(result);
  }

  audit.record(req.session.userId, req.session.username, 'task.run', `project:${project_id} cmd:${command.slice(0,60)}`, req.ip);
  res.json(result);
});

// GET /api/tasks/logs?project_id=&page=
router.get('/logs', (req, res) => {
  const { project_id, page } = req.query;
  if (!project_id) return res.status(400).json({ error: 'project_id required' });

  const pg     = Math.max(1, parseInt(page) || 1);
  const limit  = 20;
  const offset = (pg - 1) * limit;

  const data = taskSvc.getProjectLogs(project_id, req.session.userId, { limit, offset });
  if (!data) return res.status(403).json({ error: 'Access denied' });

  res.json({ logs: data.rows, total: data.total, page: pg });
});

// GET /api/tasks/approved — returns the approved command list
router.get('/approved', (req, res) => {
  res.json({ commands: taskSvc.APPROVED_COMMANDS });
});

// POST /api/tasks/lint — static check only, does not execute
router.post('/lint', (req, res) => {
  const { command } = req.body;
  if (!command || typeof command !== 'string') {
    return res.status(400).json({ error: 'command required' });
  }
  const approved = taskSvc.APPROVED_COMMANDS;
  const token    = command.trim().split(/\s+/)[0];
  const ok       = approved.includes(token);
  res.json({ command, approved_token: token, passes_lint: ok, approved_list: approved });
});

module.exports = router;