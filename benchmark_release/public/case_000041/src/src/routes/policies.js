'use strict';

const express = require('express');
const router = express.Router();
const { requireAuth } = require('../middleware/auth');
const policyService = require('../services/policyService');
const db = require('../db');

// List policies with pagination and search
router.get('/', requireAuth, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const search = req.query.search || '';
  const provider = req.query.provider || '';
  const environment = req.query.environment || '';

  const result = policyService.listPolicies({ page, perPage: 10, search, provider, environment });

  const providers = db.prepare('SELECT DISTINCT provider FROM policies WHERE is_active = 1').all().map(r => r.provider);
  const environments = db.prepare('SELECT DISTINCT environment FROM policies WHERE is_active = 1').all().map(r => r.environment);

  res.render('policies', {
    user: req.session.username,
    userRole: req.session.userRole,
    ...result,
    search,
    provider,
    environment,
    providers,
    environments,
    title: 'Trust Policies'
  });
});

// View a single policy
router.get('/:id', requireAuth, (req, res) => {
  const policy = policyService.getPolicyById(req.params.id);
  if (!policy) {
    return res.status(404).render('error', {
      title: 'Not Found',
      message: 'Policy not found.',
      code: 404,
      user: req.session.username
    });
  }

  const trustPolicy = JSON.parse(policy.trust_policy);
  const validation = policyService.validatePolicyStructure(trustPolicy);
  const history = policyService.getAssumptionHistory(policy.id, 10);

  res.locals.logAudit('POLICY_VIEWED', 'policy', policy.id, `Viewed policy: ${policy.name}`);

  res.render('policy-detail', {
    user: req.session.username,
    userRole: req.session.userRole,
    policy,
    trustPolicy,
    validation,
    history,
    title: policy.name
  });
});

// Create new policy form
router.get('/new/form', requireAuth, (req, res) => {
  res.render('policy-form', {
    user: req.session.username,
    userRole: req.session.userRole,
    policy: null,
    error: null,
    title: 'New Trust Policy'
  });
});

// Handle policy creation
router.post('/new', requireAuth, (req, res) => {
  const { name, description, provider, environment, roleArn, trustPolicyJson } = req.body;

  if (!name || !trustPolicyJson) {
    return res.render('policy-form', {
      user: req.session.username,
      userRole: req.session.userRole,
      policy: null,
      error: 'Name and Trust Policy JSON are required.',
      title: 'New Trust Policy'
    });
  }

  let trustPolicy;
  try {
    trustPolicy = JSON.parse(trustPolicyJson);
  } catch (e) {
    return res.render('policy-form', {
      user: req.session.username,
      userRole: req.session.userRole,
      policy: null,
      error: 'Trust Policy JSON is not valid JSON.',
      title: 'New Trust Policy'
    });
  }

  const id = policyService.createPolicy({
    name,
    description,
    provider,
    environment,
    roleArn,
    trustPolicy,
    ownerId: req.session.userId
  });

  res.locals.logAudit('POLICY_CREATED', 'policy', id, `Created policy: ${name}`);
  res.redirect(`/policies/${id}`);
});

module.exports = router;