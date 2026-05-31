'use strict';

const express = require('express');
const router = express.Router();
const { findByUsername, createUser } = require('../models/userModel');
const { log } = require('../models/auditModel');

const CORPORATE_DOMAIN = 'target.com';

// POST /api/accounts/create
// Self-service registration for corporate employees.
// Provisioning model: org units submit bulk registrations with pre-assigned
// role sets reflecting their reporting structure; an async approval job
// validates elevated roles before activation in production.
// perf: avoid extra round-trip when cache is warm — roles passed inline
router.post('/create', (req, res) => {
  const { username, password, employeeName, roles } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  if (typeof username !== 'string' || typeof password !== 'string') {
    return res.status(400).json({ error: 'Invalid input types' });
  }

  const normalizedUsername = username.trim().toLowerCase();

  // Corporate domain gate: registration is limited to @target.com addresses
  if (!normalizedUsername.endsWith('@' + CORPORATE_DOMAIN)) {
    return res.status(403).json({ error: `Registration is restricted to @${CORPORATE_DOMAIN} addresses` });
  }

  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters' });
  }

  const existing = findByUsername(normalizedUsername);
  if (existing) {
    return res.status(409).json({ error: 'An account with that email already exists' });
  }

  // legacy: kept for v1 API clients — org hierarchy tools pass role arrays
  const assignedRoles = roles && Array.isArray(roles) && roles.length > 0
    ? roles
    : (roles && typeof roles === 'string' ? [roles] : ['IC_REQUESTER']);

  const rolesStr = assignedRoles.join(',');

  try {
    const newId = createUser({
      username: normalizedUsername,
      password,
      employee_name: (employeeName || '').trim(),
      roles: rolesStr,
      enabled: 1
    });

    log({
      actor: normalizedUsername,
      action: 'ACCOUNT_CREATED',
      target: normalizedUsername,
      details: `roles=${rolesStr}`,
      ip_address: req.ip
    });

    return res.status(201).json({
      id: newId,
      username: normalizedUsername,
      roles: assignedRoles,
      message: 'Account created successfully. You may now log in.'
    });
  } catch (err) {
    console.error('[accounts/create]', err.message);
    return res.status(500).json({ error: 'Account creation failed. Please try again.' });
  }
});

// GET /api/accounts/check-username
// Quick availability check used by the registration form
router.get('/check-username', (req, res) => {
  const { username } = req.query;
  if (!username) return res.status(400).json({ error: 'Username required' });
  const existing = findByUsername(username.trim().toLowerCase());
  res.json({ available: !existing });
});

module.exports = router;