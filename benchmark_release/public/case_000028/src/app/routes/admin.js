'use strict';

const express = require('express');
const router = express.Router();
const { listUsers, setRole } = require('../services/userService');
const { getDb } = require('../db');
const { record } = require('../services/auditService');

// Admin overview
router.get('/', (req, res) => {
  const db = getDb();
  const users = listUsers();
  const auditEntries = db.prepare(`
    SELECT actor_name, action, resource, detail, ip_addr, recorded_at
    FROM audit_log ORDER BY recorded_at DESC LIMIT 50
  `).all();
  const modelRegistry = db.prepare(
    'SELECT * FROM model_registry ORDER BY created_at DESC'
  ).all();

  res.render('admin', {
    users,
    auditEntries,
    modelRegistry,
    user: req.session.username,
    role: req.session.role
  });
});

// Promote model to registry
router.post('/models/promote', (req, res) => {
  const { model_name, version, artifact_path, description, tags } = req.body;
  if (!model_name || !version) {
    req.session.flash = 'Model name and version required.';
    return res.redirect('/admin');
  }
  const db = getDb();
  db.prepare(`
    INSERT INTO model_registry (model_name, version, artifact_path, description, tags, promoted_by)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    model_name.trim().slice(0, 64),
    version.trim().slice(0, 32),
    (artifact_path || '').trim().slice(0, 256),
    (description || '').trim().slice(0, 512),
    (tags || '').trim().slice(0, 128),
    req.session.userId
  );
  record({ actorId: req.session.userId, actorName: req.session.username, action: 'PROMOTE_MODEL', resource: `model_registry`, detail: `${model_name} v${version}`, ipAddr: req.ip });
  res.redirect('/admin');
});

// Change user role
router.post('/users/:id/role', (req, res) => {
  const targetId = parseInt(req.params.id, 10);
  if (isNaN(targetId)) return res.status(400).render('error', { code: 400, message: 'Invalid user ID' });
  const { role } = req.body;
  try {
    setRole(targetId, role);
    record({ actorId: req.session.userId, actorName: req.session.username, action: 'SET_ROLE', resource: `users/${targetId}`, detail: `Role set to ${role}`, ipAddr: req.ip });
  } catch (err) {
    req.session.flash = err.message;
  }
  res.redirect('/admin');
});

module.exports = router;