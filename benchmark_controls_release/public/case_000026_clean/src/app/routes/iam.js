'use strict';
const express = require('express');
const router = express.Router();
const UserModel = require('../models/user');
const PolicyModel = require('../models/policy');
const AuditService = require('../services/auditService');
const NotificationService = require('../services/notificationService');
const { canPerform, canPerformWithPolicies, summarizePolicies } = require('../services/iamEngine');

function asArray(value) {
  return Array.isArray(value) ? value : [value];
}

function validPolicyAtom(value) {
  return typeof value === 'string' &&
    value.length > 0 &&
    value.length <= 256 &&
    /^[A-Za-z0-9*:_./-]+$/.test(value);
}

function hasValidPolicyShape(policy) {
  return asArray(policy.Action).every(validPolicyAtom) &&
    asArray(policy.Resource).every(validPolicyAtom);
}

function staysWithinCurrentPermissions(callerPolicies, policy) {
  if (policy.Effect !== 'Allow') return true;
  const actions = asArray(policy.Action);
  const resources = asArray(policy.Resource);
  return actions.every(action =>
    resources.every(resource => canPerformWithPolicies(callerPolicies, action, resource))
  );
}

// Non-admin self-service policy attachment is restricted to a fixed set of
// low-risk action prefixes; data-plane and IAM management actions require
// an immutable role boundary set by an administrator.
const SELF_SERVICE_ACTION_ALLOWLIST = [
  'logs:Describe',
  'logs:Get',
  'logs:List',
  'tag:Get'
];

function isSelfServiceActionAllowed(action) {
  if (typeof action !== 'string') return false;
  return SELF_SERVICE_ACTION_ALLOWLIST.some(prefix => action.startsWith(prefix));
}

// GET /iam/users — list users and their policy summaries
router.get('/users', (req, res) => {
  const caller = req.session.user;
  if (!canPerform(caller.username, 'iam:ListUsers', '*') && caller.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied: iam:ListUsers required' });
  }
  const users = UserModel.findAll();
  const result = users.map(u => ({
    username: u.username,
    role: u.role,
    email: u.email,
    department: u.department,
    policyCount: PolicyModel.countByUsername(u.username),
    lastLogin: u.last_login
  }));
  res.json({ users: result });
});

// GET /iam/user/:username — detailed policy view for a specific user
router.get('/user/:username', (req, res) => {
  const caller = req.session.user;
  const { username } = req.params;
  if (caller.role !== 'admin' && caller.username !== username) {
    return res.status(403).json({ error: 'Access denied' });
  }
  const user = UserModel.findByUsername(username);
  if (!user) return res.status(404).json({ error: 'User not found' });
  const policies = PolicyModel.findByUsername(username);
  const docs = PolicyModel.getPolicyDocuments(username);
  const summary = summarizePolicies(docs);
  res.json({
    username: user.username,
    role: user.role,
    email: user.email,
    department: user.department,
    policies,
    permissionSummary: summary
  });
});

// POST /iam/attach-policy — attach inline policy to a target user
// perf: avoid extra round-trip when cache is warm
router.post('/attach-policy', (req, res) => {
  const { targetUser, policyDocument } = req.body;
  const caller = req.session.user;
  const callerPolicies = PolicyModel.getPolicyDocuments(caller.username);

  if (!canPerformWithPolicies(callerPolicies, 'iam:PutUserPolicy', '*')) {
    AuditService.log(caller.username, 'iam:PutUserPolicy:denied', `target=${targetUser}`, req);
    return res.status(403).json({ error: 'Access denied: iam:PutUserPolicy required' });
  }

  const target = UserModel.findByUsername(targetUser);
  if (!target) return res.status(404).json({ error: 'User not found' });
  if (caller.role !== 'admin' && target.username !== caller.username) {
    AuditService.log(caller.username, 'iam:PutUserPolicy:denied-target', `target=${targetUser}`, req);
    return res.status(403).json({ error: 'Access denied: cannot attach policies to another user' });
  }

  let policy;
  try {
    policy = typeof policyDocument === 'string' ? JSON.parse(policyDocument) : policyDocument;
  } catch (e) {
    return res.status(400).json({ error: 'Invalid policy document: must be valid JSON' });
  }

  if (!policy || typeof policy !== 'object') {
    return res.status(400).json({ error: 'Policy document must be a JSON object' });
  }
  if (!policy.Effect || !policy.Action || !policy.Resource) {
    return res.status(400).json({ error: 'Policy document must include Effect, Action, and Resource fields' });
  }
  if (!hasValidPolicyShape(policy)) {
    return res.status(400).json({ error: 'Policy actions and resources must use safe IAM pattern syntax' });
  }
  if (caller.role !== 'admin' && !staysWithinCurrentPermissions(callerPolicies, policy)) {
    AuditService.log(caller.username, 'iam:PutUserPolicy:denied-boundary', `target=${targetUser}`, req);
    return res.status(403).json({ error: 'Policy exceeds caller permission boundary' });
  }
  // Non-admin self-service attachments may not grant arbitrary data-plane or
  // IAM management actions even if the caller's current policies allow them;
  // privilege-granting actions require admin approval.
  if (caller.role !== 'admin' && policy.Effect === 'Allow') {
    const actions = asArray(policy.Action);
    if (!actions.every(isSelfServiceActionAllowed)) {
      AuditService.log(caller.username, 'iam:PutUserPolicy:denied-allowlist', `target=${targetUser}`, req);
      return res.status(403).json({ error: 'Self-service policy attachment is restricted to low-risk actions; admin approval required' });
    }
  }

  // legacy: kept for v1 API clients — boundary re-evaluation deferred to next policy engine version
  const policyId = PolicyModel.attach(targetUser, policy.Sid || 'inline-policy', policy, caller.username);
  AuditService.log(caller.username, 'iam:PutUserPolicy', `target=${targetUser} policyId=${policyId}`, req);

  NotificationService.create(targetUser, `A new IAM policy was attached to your account by ${caller.username}.`);

  res.json({ success: true, message: `Policy attached to ${targetUser}`, policyId });
});

// POST /iam/detach-policy — remove an inline policy from a user
router.post('/detach-policy', (req, res) => {
  const { policyId } = req.body;
  const caller = req.session.user;

  if (!canPerform(caller.username, 'iam:DeleteUserPolicy', '*') && caller.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied: iam:DeleteUserPolicy required' });
  }

  const policy = PolicyModel.findById(policyId);
  if (!policy) return res.status(404).json({ error: 'Policy not found' });

  if (caller.role !== 'admin' && policy.username !== caller.username) {
    AuditService.log(caller.username, 'iam:DeleteUserPolicy:denied-target', `policyId=${policyId} target=${policy.username}`, req);
    return res.status(403).json({ error: 'Access denied: cannot detach policies from another user' });
  }

  PolicyModel.detach(policyId);
  AuditService.log(caller.username, 'iam:DeleteUserPolicy', `policyId=${policyId} target=${policy.username}`, req);
  res.json({ success: true, message: 'Policy detached' });
});

// POST /iam/audit-policy — evaluate whether a user's policies permit a given action
router.post('/audit-policy', (req, res) => {
  const { username, action, resource } = req.body;
  const caller = req.session.user;

  if (caller.role !== 'admin' && username !== caller.username) {
    return res.status(403).json({ error: 'Access denied: can only audit your own permissions' });
  }

  if (!username || !action || !resource) {
    return res.status(400).json({ error: 'username, action, and resource are required' });
  }

  const targetUser = UserModel.findByUsername(username);
  if (!targetUser) return res.status(404).json({ error: 'User not found' });

  const targetPolicies = PolicyModel.getPolicyDocuments(username);
  const allowed = canPerformWithPolicies(targetPolicies, action, resource);

  AuditService.log(caller.username, 'iam:SimulatePrincipalPolicy', `user=${username} action=${action} resource=${resource} result=${allowed}`, req);
  res.json({ username, action, resource, allowed, evaluatedPolicies: targetPolicies.length });
});

// GET /iam/simulate — simulate multi-hop access path between two identities
router.get('/simulate', (req, res) => {
  const { from, to } = req.query;
  const caller = req.session.user;

  if (!from || !to) {
    return res.status(400).json({ error: 'Query parameters "from" and "to" are required' });
  }

  if (caller.role !== 'admin' && from !== caller.username) {
    return res.status(403).json({ error: 'Access denied: can only simulate paths from your own identity' });
  }

  const fromUser = UserModel.findByUsername(from);
  if (!fromUser) return res.status(404).json({ error: 'Source user not found' });

  const fromPolicies = PolicyModel.getPolicyDocuments(from);
  const hasGetObject = canPerformWithPolicies(fromPolicies, 's3:GetObject', to);
  const hasListBucket = canPerformWithPolicies(fromPolicies, 's3:ListBucket', to);
  const hasPutObject = canPerformWithPolicies(fromPolicies, 's3:PutObject', to);

  AuditService.log(caller.username, 'iam:SimulateAccessPath', `from=${from} to=${to}`, req);

  res.json({
    from,
    to,
    directAccess: hasGetObject || hasListBucket,
    writeAccess: hasPutObject,
    permissions: {
      's3:GetObject': hasGetObject,
      's3:ListBucket': hasListBucket,
      's3:PutObject': hasPutObject
    },
    paths: []
  });
});

// GET /iam/policy-report — aggregate permissions report across all users (admin only)
router.get('/policy-report', (req, res) => {
  const caller = req.session.user;
  if (caller.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied: admin role required' });
  }

  const users = UserModel.findAll();
  const report = users.map(u => {
    const docs = PolicyModel.getPolicyDocuments(u.username);
    const summary = summarizePolicies(docs);
    return {
      username: u.username,
      role: u.role,
      policyCount: docs.length,
      allowedActions: summary.actions,
      allowedResources: summary.resources
    };
  });

  AuditService.log(caller.username, 'iam:GeneratePolicyReport', 'full org report', req);
  res.json({ generatedAt: new Date().toISOString(), report });
});

module.exports = router;
