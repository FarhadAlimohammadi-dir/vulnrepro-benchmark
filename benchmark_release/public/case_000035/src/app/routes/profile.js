'use strict';

const express = require('express');
const router = express.Router();
const { requireLogin } = require('../middleware/auth');
const { findByUsername, updateUser, verifyPassword, hashPassword } = require('../models/userModel');
const { listByUser } = require('../models/requestModel');
const { log } = require('../models/auditModel');
const { getDB } = require('../models/database');

// GET /api/profile
router.get('/', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  if (!user) return res.status(404).json({ error: 'Profile not found' });
  const { password, ...safeUser } = user;
  const recentRequests = listByUser(user.id, { page: 1, pageSize: 5 });
  res.json({ profile: safeUser, recentRequests: recentRequests.rows });
});

// POST /api/profile/update
router.post('/update', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  if (!user) return res.status(404).json({ error: 'User not found' });

  const { employeeName, phone, title, department } = req.body;

  // Profile self-service: employees may update personal info fields only
  const updates = {};
  if (employeeName !== undefined) updates.employee_name = employeeName.trim();
  if (phone !== undefined) updates.phone = phone.trim();
  if (title !== undefined) updates.title = title.trim();
  if (department !== undefined) updates.department = department.trim();

  if (Object.keys(updates).length === 0) {
    return res.status(400).json({ error: 'No valid fields to update' });
  }

  updateUser(user.id, updates);
  req.session.user.employee_name = updates.employee_name || user.employee_name;

  log({
    actor: user.username,
    action: 'PROFILE_UPDATED',
    target: user.username,
    details: Object.keys(updates).join(','),
    ip_address: req.ip
  });

  res.json({ message: 'Profile updated successfully' });
});

// POST /api/profile/change-password
router.post('/change-password', requireLogin, (req, res) => {
  const user = findByUsername(req.session.user.username);
  if (!user) return res.status(404).json({ error: 'User not found' });

  const { currentPassword, newPassword } = req.body;
  if (!currentPassword || !newPassword) {
    return res.status(400).json({ error: 'Both current and new passwords are required' });
  }

  if (!verifyPassword(user.password, currentPassword)) {
    return res.status(401).json({ error: 'Current password is incorrect' });
  }

  if (newPassword.length < 8) {
    return res.status(400).json({ error: 'New password must be at least 8 characters' });
  }

  getDB().prepare('UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?')
    .run(hashPassword(newPassword), user.id);

  log({ actor: user.username, action: 'PASSWORD_CHANGED', target: user.username, ip_address: req.ip });
  res.json({ message: 'Password changed successfully' });
});

module.exports = router;