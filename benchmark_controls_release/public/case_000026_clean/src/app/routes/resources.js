'use strict';
const express = require('express');
const router = express.Router();
const ResourceModel = require('../models/resource');
const AuditService = require('../services/auditService');
const { canPerform, canPerformWithPolicies } = require('../services/iamEngine');
const PolicyModel = require('../models/policy');

// GET /resources — list all resources the caller is permitted to see
router.get('/', (req, res) => {
  const user = req.session.user;
  const all = ResourceModel.findAll();
  const policies = PolicyModel.getPolicyDocuments(user.username);

  const accessible = all.filter(r =>
    user.role === 'admin' ||
    canPerformWithPolicies(policies, 's3:ListBucket', r.arn) ||
    canPerformWithPolicies(policies, 's3:GetObject', r.arn)
  );

  res.json({ resources: accessible, total: accessible.length });
});

// GET /resources/search — search resources by label, description, or ARN
router.get('/search', (req, res) => {
  const { q } = req.query;
  if (!q || q.trim().length < 2) {
    return res.status(400).json({ error: 'Query must be at least 2 characters' });
  }

  const user = req.session.user;
  const results = ResourceModel.search(q.trim());
  const policies = PolicyModel.getPolicyDocuments(user.username);

  const accessible = results.filter(r =>
    user.role === 'admin' ||
    canPerformWithPolicies(policies, 's3:GetObject', r.arn) ||
    canPerformWithPolicies(policies, 's3:ListBucket', r.arn)
  );

  AuditService.log(user.username, 'resources:search', `query=${q}`, req);
  res.json({ results: accessible, count: accessible.length });
});

// GET /resources/:arn — fetch full resource data if permitted
router.get('/:arn', (req, res) => {
  const arn = decodeURIComponent(req.params.arn);
  const user = req.session.user;
  const policies = PolicyModel.getPolicyDocuments(user.username);
  const resource = ResourceModel.findByArn(arn);
  if (!resource) return res.status(404).json({ error: 'Resource not found' });

  if (
    !canPerformWithPolicies(policies, 's3:GetObject', resource.arn) &&
    user.role !== 'admin'
  ) {
    AuditService.log(user.username, 's3:GetObject:denied', resource.arn, req);
    return res.status(403).json({ error: 'Access denied: s3:GetObject required for this resource' });
  }

  const tags = ResourceModel.getTagsForArn(resource.arn);
  AuditService.log(user.username, 's3:GetObject', resource.arn, req);

  res.json({
    arn: resource.arn,
    label: resource.label,
    description: resource.description,
    data: resource.data,
    sensitivity: resource.sensitivity,
    owner: resource.owner,
    region: resource.region,
    tags
  });
});

module.exports = router;
