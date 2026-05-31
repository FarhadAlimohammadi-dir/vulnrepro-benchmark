'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth } = require('../middleware/auth');
const db = require('../db');
const policyService = require('../services/policyService');

router.get('/dashboard', requireAuth, (req, res) => {
  const recentPolicies = db.prepare(`
    SELECT p.id, p.name, p.provider, p.environment, p.updated_at
    FROM policies p
    WHERE p.is_active = 1
    ORDER BY p.updated_at DESC
    LIMIT 6
  `).all();

  const stats = {
    totalPolicies: db.prepare('SELECT COUNT(*) as cnt FROM policies WHERE is_active = 1').get().cnt,
    totalProviders: db.prepare('SELECT COUNT(*) as cnt FROM providers WHERE is_active = 1').get().cnt,
    recentAssumptions: db.prepare('SELECT COUNT(*) as cnt FROM role_assumptions WHERE created_at > datetime("now", "-7 days")').get().cnt,
    auditEntries: db.prepare('SELECT COUNT(*) as cnt FROM audit_log WHERE created_at > datetime("now", "-24 hours")').get().cnt
  };

  const notifications = db.prepare(`
    SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT 5
  `).all(req.session.userId);

  res.render('dashboard', {
    user: req.session.username,
    userRole: req.session.userRole,
    recentPolicies,
    stats,
    notifications,
    title: 'Dashboard'
  });
});

module.exports = router;