'use strict';
const express = require('express');
const router = express.Router();
const PolicyModel = require('../models/policy');
const ResourceModel = require('../models/resource');
const AuditService = require('../services/auditService');
const NotificationService = require('../services/notificationService');
const { canPerform } = require('../services/iamEngine');

router.get('/', (req, res) => {
  const user = req.session.user;
  const policies = PolicyModel.findByUsername(user.username);
  const allResources = ResourceModel.findAll();
  const notifications = NotificationService.getUnread(user.username);
  const recentActivity = AuditService.getLogsByActor(user.username, 5);

  // Determine which resources the current user can access
  const accessibleArns = allResources
    .filter(r => canPerform(user.username, 's3:GetObject', r.arn) || canPerform(user.username, 's3:ListBucket', r.arn) || user.role === 'admin')
    .map(r => r.arn);

  res.render('dashboard', {
    title: 'CloudLens Dashboard',
    user,
    policies,
    allResources,
    accessibleArns,
    notifications,
    recentActivity,
    policyCount: policies.length
  });
});

module.exports = router;