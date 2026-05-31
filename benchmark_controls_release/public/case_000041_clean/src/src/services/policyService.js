'use strict';

const db = require('../db');
const { v4: uuidv4 } = require('uuid');

/**
 * Retrieve a policy by its ID, including owner information.
 */
function getPolicyById(id) {
  return db.prepare(`
    SELECT p.*, u.username as owner_name, u.full_name as owner_full_name
    FROM policies p
    LEFT JOIN users u ON p.owner_id = u.id
    WHERE p.id = ?
  `).get(id);
}

/**
 * List policies with optional filtering and pagination.
 */
function listPolicies({ page = 1, perPage = 10, provider, environment, search, ownerId, includeAll = false } = {}) {
  const offset = (page - 1) * perPage;
  let where = 'WHERE p.is_active = 1';
  const params = [];

  if (!includeAll) {
    where += ' AND p.owner_id = ?';
    params.push(ownerId);
  }

  if (provider) {
    where += ' AND p.provider = ?';
    params.push(provider);
  }
  if (environment) {
    where += ' AND p.environment = ?';
    params.push(environment);
  }
  if (search) {
    where += ' AND (p.name LIKE ? OR p.description LIKE ?)';
    params.push(`%${search}%`, `%${search}%`);
  }

  const total = db.prepare(`
    SELECT COUNT(*) as cnt FROM policies p ${where}
  `).get(...params).cnt;

  const items = db.prepare(`
    SELECT p.id, p.name, p.description, p.provider, p.environment, p.role_arn,
           p.tags, p.created_at, p.updated_at, p.last_evaluated,
           u.username as owner_name
    FROM policies p
    LEFT JOIN users u ON p.owner_id = u.id
    ${where}
    ORDER BY p.updated_at DESC
    LIMIT ? OFFSET ?
  `).all(...params, perPage, offset);

  return {
    items,
    total,
    page,
    perPage,
    totalPages: Math.ceil(total / perPage)
  };
}

/**
 * Create a new trust policy record.
 */
function createPolicy({ name, description, provider, environment, roleArn, trustPolicy, ownerId, tags }) {
  const result = db.prepare(`
    INSERT INTO policies (name, description, provider, environment, role_arn, trust_policy, owner_id, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(name, description, provider, environment, roleArn, JSON.stringify(trustPolicy), ownerId, JSON.stringify(tags || []));

  return result.lastInsertRowid;
}

/**
 * Update an existing policy's trust document.
 */
function updatePolicy(id, { name, description, trustPolicy, tags }) {
  db.prepare(`
    UPDATE policies
    SET name = ?, description = ?, trust_policy = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `).run(name, description, JSON.stringify(trustPolicy), JSON.stringify(tags || []), id);
}

/**
 * Soft-delete a policy by marking it inactive.
 */
function deactivatePolicy(id) {
  db.prepare('UPDATE policies SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(id);
}

/**
 * Record a role assumption attempt.
 */
function recordAssumptionAttempt({ userId, policyId, subjectClaim, audienceClaim, result, sessionToken }) {
  db.prepare(`
    INSERT INTO role_assumptions (user_id, policy_id, subject_claim, audience_claim, result, session_token)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(userId, policyId, subjectClaim || '', audienceClaim || '', result, sessionToken || '');
}

/**
 * Fetch assumption history for a specific policy.
 */
function getAssumptionHistory(policyId, limit = 20) {
  return db.prepare(`
    SELECT ra.*, u.username
    FROM role_assumptions ra
    LEFT JOIN users u ON ra.user_id = u.id
    WHERE ra.policy_id = ?
    ORDER BY ra.created_at DESC
    LIMIT ?
  `).all(policyId, limit);
}

/**
 * Validate structural completeness of a trust policy document.
 * Returns { valid: bool, issues: string[] }
 */
function validatePolicyStructure(policy) {
  const issues = [];

  if (!policy.Effect) issues.push('Missing Effect field');
  if (policy.Effect && !['Allow', 'Deny'].includes(policy.Effect)) issues.push('Effect must be Allow or Deny');
  if (!policy.Principal) issues.push('Missing Principal field');
  if (!policy.Action) issues.push('Missing Action field');
  if (!policy.Condition) issues.push('Missing Condition block — conditions are required for OIDC policies');

  if (policy.Condition) {
    const se = policy.Condition.StringEquals || {};
    const keys = Object.keys(se);
    const hasAud = keys.some(k => k.endsWith(':aud'));
    const hasSub = keys.some(k => k.endsWith(':sub'));
    if (!hasAud) issues.push('No :aud (audience) condition found in StringEquals');
    if (!hasSub) issues.push('No :sub (subject) condition found — restricts which identities can assume this role');
  }

  return { valid: issues.length === 0, issues };
}

module.exports = {
  getPolicyById,
  listPolicies,
  createPolicy,
  updatePolicy,
  deactivatePolicy,
  recordAssumptionAttempt,
  getAssumptionHistory,
  validatePolicyStructure
};
