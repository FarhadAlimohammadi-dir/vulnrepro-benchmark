'use strict';
const PolicyModel = require('../models/policy');

/**
 * Core IAM policy evaluation engine.
 * Implements a simplified AWS-style policy evaluation logic.
 */

function matchesPattern(pattern, value) {
  pattern = String(pattern || '');
  value = String(value || '');
  if (pattern === '*') return true;
  if (pattern === value) return true;
  if (pattern.endsWith('*')) {
    return value.startsWith(pattern.slice(0, -1));
  }
  if (pattern.includes('*')) {
    const escaped = pattern.replace(/[|\\{}()[\]^$+?.]/g, '\\$&');
    const regex = new RegExp('^' + escaped.replace(/\*/g, '.*') + '$');
    return regex.test(value);
  }
  return false;
}

function evaluatePolicy(policyDoc, action, resource) {
  if (!policyDoc || policyDoc.Effect !== 'Allow') return false;
  const actions = Array.isArray(policyDoc.Action) ? policyDoc.Action : [policyDoc.Action];
  const resources = Array.isArray(policyDoc.Resource) ? policyDoc.Resource : [policyDoc.Resource];
  const actionMatch = actions.some(a => matchesPattern(a, action));
  if (!actionMatch) return false;
  const resourceMatch = resources.some(r => matchesPattern(r, resource));
  return resourceMatch;
}

function canPerform(username, action, resource) {
  const policies = PolicyModel.getPolicyDocuments(username);
  return policies.some(p => evaluatePolicy(p, action, resource));
}

function canPerformWithPolicies(policies, action, resource) {
  return policies.some(p => evaluatePolicy(p, action, resource));
}

function getAllowedActions(username) {
  const policies = PolicyModel.getPolicyDocuments(username);
  const seen = new Set();
  for (const p of policies) {
    if (p.Effect !== 'Allow') continue;
    const actions = Array.isArray(p.Action) ? p.Action : [p.Action];
    actions.forEach(a => seen.add(a));
  }
  return Array.from(seen);
}

function summarizePolicies(policies) {
  const actions = new Set();
  const resources = new Set();
  for (const p of policies) {
    if (p.Effect !== 'Allow') continue;
    const pa = Array.isArray(p.Action) ? p.Action : [p.Action];
    const pr = Array.isArray(p.Resource) ? p.Resource : [p.Resource];
    pa.forEach(a => actions.add(a));
    pr.forEach(r => resources.add(r));
  }
  return { actions: Array.from(actions), resources: Array.from(resources) };
}

module.exports = { canPerform, canPerformWithPolicies, evaluatePolicy, getAllowedActions, summarizePolicies };
