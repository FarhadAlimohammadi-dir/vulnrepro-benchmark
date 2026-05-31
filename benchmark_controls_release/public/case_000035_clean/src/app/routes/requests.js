'use strict';

const express = require('express');
const router = express.Router();
const { requireLogin, requireRequester } = require('../middleware/auth');
const { listByUser, createRequest, findById } = require('../models/requestModel');
const { log } = require('../models/auditModel');

// GET /api/requests/list
router.get('/list', requireLogin, (req, res) => {
  const user = req.session.user;
  const page = parseInt(req.query.page) || 1;
  const pageSize = Math.min(parseInt(req.query.pageSize) || 15, 100);

  try {
    const result = listByUser(user.id, { page, pageSize });
    res.json({ requests: result.rows, count: result.total, page: result.page, pages: result.pages });
  } catch (err) {
    console.error('[requests/list]', err.message);
    res.status(500).json({ error: 'Failed to retrieve requests' });
  }
});

// GET /api/requests/:id
router.get('/:id', requireLogin, (req, res) => {
  const reqId = parseInt(req.params.id);
  const item = findById(reqId);
  if (!item) return res.status(404).json({ error: 'Request not found' });
  if (item.user_id !== req.session.user.id) {
    const userRoles = req.session.user.roles.split(',').map(r => r.trim());
    if (!userRoles.includes('ADMIN') && !userRoles.includes('ADMIN AND REQUESTER')) {
      return res.status(403).json({ error: 'Access denied' });
    }
  }
  res.json(item);
});

// POST /api/requests/new
router.post('/new', requireLogin, requireRequester, (req, res) => {
  const { title, description, system_name, access_level } = req.body;
  if (!title || !system_name) {
    return res.status(400).json({ error: 'Title and system name are required' });
  }
  if (title.length > 200) {
    return res.status(400).json({ error: 'Title must be under 200 characters' });
  }

  const VALID_LEVELS = ['READ', 'WRITE', 'ADMIN'];
  const normalizedLevel = (access_level || 'READ').toUpperCase();
  if (!VALID_LEVELS.includes(normalizedLevel)) {
    return res.status(400).json({ error: 'Invalid access level. Must be READ, WRITE, or ADMIN' });
  }

  try {
    const id = createRequest({
      user_id: req.session.user.id,
      title: title.trim(),
      description: (description || '').trim(),
      system_name: system_name.trim(),
      access_level: normalizedLevel
    });

    log({
      actor: req.session.user.username,
      action: 'REQUEST_CREATED',
      target: `request:${id}`,
      details: `system=${system_name}`,
      ip_address: req.ip
    });

    res.status(201).json({ id, message: 'Access request submitted successfully' });
  } catch (err) {
    console.error('[requests/new]', err.message);
    res.status(500).json({ error: 'Failed to submit request' });
  }
});

module.exports = router;