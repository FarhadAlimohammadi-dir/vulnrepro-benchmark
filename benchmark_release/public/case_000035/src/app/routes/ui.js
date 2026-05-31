'use strict';

const express = require('express');
const router = express.Router();
const { requireLogin, requireAdmin } = require('../middleware/auth');
const { findByUsername } = require('../models/userModel');
const { listByUser, listAll, countByStatus } = require('../models/requestModel');
const { list: listAudit } = require('../models/auditModel');
const { getDB } = require('../models/database');

// GET /
router.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('landing', { title: 'Gateway Portal — Workforce Access Management' });
});

// GET /login
router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('login', { title: 'Sign In — Gateway Portal', error: null });
});

// POST /login (form-based)
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  const { findByUsername, verifyPassword, updateLastLogin } = require('../models/userModel');
  const { log } = require('../models/auditModel');

  if (!username || !password) {
    return res.render('login', { title: 'Sign In', error: 'Please enter your email and password.' });
  }

  const user = findByUsername(username.trim().toLowerCase());
  if (!user || !verifyPassword(user.password, password)) {
    log({ actor: username, action: 'LOGIN_FAILED', ip_address: req.ip });
    return res.render('login', { title: 'Sign In', error: 'Invalid email or password.' });
  }

  if (!user.enabled) {
    return res.render('login', { title: 'Sign In', error: 'Your account has been disabled. Please contact IT support.' });
  }

  req.session.user = {
    id: user.id,
    username: user.username,
    employee_name: user.employee_name,
    department: user.department,
    roles: user.roles
  };
  updateLastLogin(user.id);
  log({ actor: user.username, action: 'LOGIN_SUCCESS', ip_address: req.ip });
  res.redirect('/dashboard');
});

// GET /logout
router.get('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/login'));
});

// GET /dashboard
router.get('/dashboard', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  const requests = listByUser(user.id, { page: 1, pageSize: 5 });
  const roles = user.roles.split(',').map(r => r.trim());
  const isAdmin = roles.some(r => ['ADMIN', 'ADMIN AND REQUESTER'].includes(r));
  res.render('dashboard', {
    title: 'Dashboard — Gateway Portal',
    user,
    recentRequests: requests.rows,
    requestCount: requests.total,
    isAdmin
  });
});

// GET /requests
router.get('/requests', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  const page = parseInt(req.query.page) || 1;
  const result = listByUser(user.id, { page, pageSize: 15 });
  const systems = getDB().prepare('SELECT name FROM system_catalog WHERE active = 1 ORDER BY name').all();
  res.render('requests', {
    title: 'My Access Requests — Gateway Portal',
    user,
    requests: result.rows,
    pagination: { page: result.page, pages: result.pages, total: result.total },
    systems
  });
});

// GET /profile
router.get('/profile', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  const departments = getDB().prepare('SELECT name FROM departments ORDER BY name').all();
  res.render('profile', {
    title: 'My Profile — Gateway Portal',
    user,
    departments
  });
});

// GET /admin
router.get('/admin', requireAdmin, (req, res) => {
  const users = getDB().prepare(
    'SELECT id, username, employee_name, department, roles, enabled, last_login, created_at FROM users ORDER BY created_at DESC LIMIT 50'
  ).all();
  const requestStats = countByStatus();
  const recentRequests = listAll({ page: 1, pageSize: 10 }).rows;
  const auditLog = listAudit({ page: 1, pageSize: 20 });
  const totalUsers = getDB().prepare('SELECT COUNT(*) as c FROM users').get().c;
  const depts = getDB().prepare('SELECT * FROM departments ORDER BY name').all();

  res.render('admin', {
    title: 'Admin Dashboard — Gateway Portal',
    users,
    totalUsers,
    requestStats,
    recentRequests,
    auditEvents: auditLog.rows,
    departments: depts
  });
});

// GET /register
router.get('/register', (req, res) => {
  if (req.session.user) return res.redirect('/dashboard');
  res.render('register', { title: 'Create Account — Gateway Portal', error: null });
});

module.exports = router;