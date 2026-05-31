'use strict';

const express = require('express');
const router = express.Router();
const { findByUsername, verifyPassword, updateLastLogin } = require('../models/userModel');
const { log } = require('../models/auditModel');

// POST /api/auth/login
router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  const user = findByUsername(username.trim().toLowerCase());

  if (!user || !verifyPassword(user.password, password)) {
    log({ actor: username, action: 'LOGIN_FAILED', target: '', ip_address: req.ip });
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  if (!user.enabled) {
    return res.status(403).json({ error: 'Account is disabled. Contact your administrator.' });
  }

  req.session.user = {
    id: user.id,
    username: user.username,
    employee_name: user.employee_name,
    department: user.department,
    roles: user.roles
  };

  updateLastLogin(user.id);
  log({ actor: user.username, action: 'LOGIN_SUCCESS', target: '', ip_address: req.ip });

  return res.json({
    message: 'Login successful',
    username: user.username,
    employeeName: user.employee_name,
    roles: user.roles.split(',').map(r => r.trim())
  });
});

// POST /api/auth/logout
router.post('/logout', (req, res) => {
  const actor = req.session.user ? req.session.user.username : 'anonymous';
  log({ actor, action: 'LOGOUT', ip_address: req.ip });
  req.session.destroy(() => {
    res.json({ message: 'Logged out successfully' });
  });
});

// GET /api/auth/me
router.get('/me', (req, res) => {
  if (!req.session.user) {
    return res.status(401).json({ error: 'Not authenticated' });
  }
  const u = req.session.user;
  res.json({ username: u.username, employeeName: u.employee_name, roles: u.roles.split(',').map(r => r.trim()), department: u.department });
});

module.exports = router;