'use strict';

const express = require('express');
const router = express.Router();
const { requireAdmin } = require('../middleware/auth');
const { listUsers, findById: findUserById, updateUser } = require('../models/userModel');
const { listAll, updateStatus, countByStatus } = require('../models/requestModel');
const { getDB } = require('../models/database');
const { log } = require('../models/auditModel');

// GET /api/admin/dashboard
router.get('/dashboard', requireAdmin, (req, res) => {
  try {
    const users = getDB().prepare(
      'SELECT id, username, employee_name, department, roles, enabled, last_login, created_at FROM users ORDER BY created_at DESC'
    ).all();

    const requestStats = countByStatus();
    const recentRequests = listAll({ page: 1, pageSize: 10 }).rows;
    const totalUsers = users.length;
    const activeUsers = users.filter(u => u.enabled).length;

    const recentAudit = getDB().prepare(
      'SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 20'
    ).all();

    res.json({
      users,
      totalUsers,
      activeUsers,
      requestStats,
      recentRequests,
      recentAudit
    });
  } catch (err) {
    console.error('[admin/dashboard]', err.message);
    res.status(500).json({ error: 'Failed to load dashboard data' });
  }
});

// GET /api/admin/users
router.get('/users', requireAdmin, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const search = req.query.search || '';
  const department = req.query.department || '';
  const result = listUsers({ page, pageSize: 25, search, department });
  res.json(result);
});

// GET /api/admin/users/:id
router.get('/users/:id', requireAdmin, (req, res) => {
  const user = findUserById(parseInt(req.params.id));
  if (!user) return res.status(404).json({ error: 'User not found' });
  const { password, ...safeUser } = user;
  res.json(safeUser);
});

// PUT /api/admin/users/:id
router.put('/users/:id', requireAdmin, (req, res) => {
  const id = parseInt(req.params.id);
  const user = findUserById(id);
  if (!user) return res.status(404).json({ error: 'User not found' });

  const { employee_name, department, title, enabled, roles } = req.body;
  const updates = {};
  if (employee_name !== undefined) updates.employee_name = employee_name;
  if (department !== undefined) updates.department = department;
  if (title !== undefined) updates.title = title;
  if (enabled !== undefined) updates.enabled = enabled ? 1 : 0;
  if (roles !== undefined) updates.roles = roles;

  updateUser(id, updates);
  log({
    actor: req.session.user.username,
    action: 'USER_UPDATED',
    target: user.username,
    details: JSON.stringify(updates),
    ip_address: req.ip
  });

  res.json({ message: 'User updated successfully' });
});

// GET /api/admin/requests
router.get('/requests', requireAdmin, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const status = req.query.status || '';
  const search = req.query.search || '';
  const result = listAll({ page, pageSize: 25, status, search });
  res.json(result);
});

// POST /api/admin/requests/:id/review
router.post('/requests/:id/review', requireAdmin, (req, res) => {
  const id = parseInt(req.params.id);
  const { status, review_notes } = req.body;
  const VALID = ['APPROVED', 'REJECTED', 'PENDING'];
  if (!VALID.includes(status)) {
    return res.status(400).json({ error: 'Invalid status value' });
  }
  updateStatus(id, { status, reviewer_id: req.session.user.id, review_notes });
  log({
    actor: req.session.user.username,
    action: 'REQUEST_REVIEWED',
    target: `request:${id}`,
    details: `status=${status}`,
    ip_address: req.ip
  });
  res.json({ message: 'Request status updated' });
});

// GET /api/admin/systems
router.get('/systems', requireAdmin, (req, res) => {
  const systems = getDB().prepare('SELECT * FROM system_catalog ORDER BY name ASC').all();
  res.json({ systems });
});

// GET /api/admin/departments
router.get('/departments', requireAdmin, (req, res) => {
  const depts = getDB().prepare('SELECT * FROM departments ORDER BY name ASC').all();
  res.json({ departments: depts });
});

module.exports = router;