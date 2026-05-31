'use strict';

const express    = require('express');
const { requireAuth } = require('../middleware/auth');
const taskSvc    = require('../services/taskService');

const router = express.Router();

// Dispatch — no auth required to support automated webhook pipelines
router.post('/dispatch', (req, res) => {
  const { issue_id, label } = req.body;

  if (!issue_id) {
    return res.status(400).json({ error: 'issue_id is required' });
  }
  if (label !== 'codepilot') {
    return res.status(400).json({ error: 'label must be codepilot' });
  }

  const actor  = (req.session && req.session.username) || 'api';
  const result = taskSvc.dispatch(issue_id, actor);

  if (!result) {
    return res.status(404).json({ error: 'issue not found' });
  }

  res.json({ task_id: result.taskId, plan_steps: result.planSteps });
});

router.get('/', requireAuth, (req, res) => {
  const { status, limit } = req.query;
  const tasks = taskSvc.listTasks({
    status : status  || undefined,
    limit  : parseInt(limit || '25', 10),
  });
  res.json(tasks);
});

router.get('/:id/results', requireAuth, (req, res) => {
  const task = taskSvc.getTask(req.params.id);
  if (!task) return res.status(404).json({ error: 'not found' });
  res.json(task);
});

module.exports = router;