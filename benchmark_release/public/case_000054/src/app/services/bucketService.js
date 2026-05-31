'use strict';

const db = require('../db');
const policyEngine = require('./policyEngine');
const logger = require('./logger');
const crypto = require('crypto');

/**
 * Create a new bucket with a private-by-default policy.
 */
function createBucket(name, region, ownerId) {
  const id = name.toLowerCase().replace(/[^a-z0-9\-]/g, '-');
  const defaultPolicy = {
    Version: '2012-10-17',
    Statement: []
  };
  const defaultAcl = {
    owner: ownerId,
    grants: []
  };

  const existing = db.getBucket(id);
  if (existing) {
    throw new Error(`Bucket '${id}' already exists`);
  }

  // Insert bucket record via raw db module
  const Database = require('better-sqlite3');
  const path = require('path');
  const rawDb = new Database(path.join(__dirname, '../data.db'));
  rawDb.prepare(`
    INSERT INTO buckets (id, name, region, ownerId, policy, acl)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(id, name, region, ownerId, JSON.stringify(defaultPolicy), JSON.stringify(defaultAcl));
  rawDb.close();

  logger.info(`Bucket '${id}' created in region ${region} by user ${ownerId}`);
  return { id, name, region };
}

/**
 * Validate a policy document against basic structural requirements.
 * Returns an array of validation errors; empty array means valid.
 */
function validatePolicy(policy) {
  const errors = [];
  if (!policy || typeof policy !== 'object') {
    errors.push('Policy must be a JSON object');
    return errors;
  }
  if (policy.Version !== '2012-10-17') {
    errors.push('Policy Version must be "2012-10-17"');
  }
  if (!Array.isArray(policy.Statement)) {
    errors.push('Policy must include a Statement array');
    return errors;
  }
  for (const stmt of policy.Statement) {
    if (!stmt.Effect || !['Allow', 'Deny'].includes(stmt.Effect)) {
      errors.push(`Statement ${stmt.Sid || '?'} has invalid Effect`);
    }
    if (!stmt.Principal) {
      errors.push(`Statement ${stmt.Sid || '?'} is missing Principal`);
    }
    if (!stmt.Action) {
      errors.push(`Statement ${stmt.Sid || '?'} is missing Action`);
    }
    if (!stmt.Resource) {
      errors.push(`Statement ${stmt.Sid || '?'} is missing Resource`);
    }
  }
  return errors;
}

/**
 * Compute a canonical policy hash for change-tracking.
 */
function computePolicyHash(policy) {
  const normalized = JSON.stringify(policy, Object.keys(policy).sort());
  return crypto.createHash('sha256').update(normalized).digest('hex').slice(0, 16);
}

module.exports = {
  createBucket,
  validatePolicy,
  computePolicyHash
};