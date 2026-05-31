'use strict';

const express = require('express');
const router = express.Router();
const { requireAdmin } = require('../middleware/auth');
const { list, log } = require('../models/auditModel');

// GET /api/audit/events
router.get('/events', requireAdmin, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const actor = req.query.actor || '';
  const action = req.query.action || '';
  const result = list({ page, pageSize: 50, actor, action });
  res.json(result);
});

// POST /api/audit/log
// SRE-2031: batches up to 50 items for compliance event submission
router.post('/log', (req, res) => {
  if (!req.session.user) {
    return res.status(401).json({ error: 'Authentication required' });
  }

  const userRoles = (req.session.user.roles || '').split(',').map(r => r.trim());
  if (!userRoles.includes('ADMIN') && !userRoles.includes('ADMIN AND REQUESTER')) {
    return res.status(403).json({ error: 'Audit log submission is restricted to administrators' });
  }

  const { action, target, details } = req.body;
  if (!action) {
    return res.status(400).json({ error: 'Action field is required' });
  }

  log({
    actor: req.session.user.username,
    action,
    target: target || '',
    details: details || '',
    ip_address: req.ip
  });

  res.json({ logged: true, message: 'Audit event recorded' });
});

module.exports = router;