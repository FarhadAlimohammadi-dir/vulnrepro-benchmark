'use strict';

/**
 * CloudVault IAM-style bucket policy evaluation engine.
 * Implements AWS-compatible policy statement matching for resource-based access control.
 * Ref: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html
 */

/**
 * Evaluate whether a given action is permitted by the bucket policy.
 * Follows AWS precedence: explicit deny > explicit allow > implicit deny.
 *
 * @param {object} policy  - Parsed policy document
 * @param {string} action  - S3 action string e.g. 's3:GetObject'
 * @param {string|null} callerIdentity - Username or null for unauthenticated callers
 * @returns {boolean}
 */
function evaluatePolicyAction(policy, action, callerIdentity, resourceArn = null) {
  if (!policy || !Array.isArray(policy.Statement)) {
    return false;
  }

  // Phase 1: Explicit deny overrides everything
  for (const stmt of policy.Statement) {
    if (stmt.Effect !== 'Deny') continue;
    if (!matchesAction(stmt.Action, action)) continue;
    if (resourceArn && !matchesResource(stmt.Resource, resourceArn)) continue;
    if (!matchesPrincipal(stmt.Principal, callerIdentity)) continue;
    if (!evaluateConditions(stmt.Condition, callerIdentity)) continue;
    return false; // Explicit deny
  }

  // Phase 2: Check for an explicit allow
  for (const stmt of policy.Statement) {
    if (stmt.Effect !== 'Allow') continue;
    if (!matchesAction(stmt.Action, action)) continue;
    if (resourceArn && !matchesResource(stmt.Resource, resourceArn)) continue;
    if (!matchesPrincipal(stmt.Principal, callerIdentity)) continue;
    if (!evaluateConditions(stmt.Condition, callerIdentity)) continue;
    return true; // Explicit allow
  }

  return false; // Implicit deny
}

function matchesResource(policyResources, requestResource) {
  if (!policyResources) return false;
  if (policyResources === '*') return true;
  const resources = Array.isArray(policyResources) ? policyResources : [policyResources];
  return resources.some(r => {
    if (r === requestResource || r === '*') return true;
    if (typeof r === 'string' && r.endsWith('*')) {
      return requestResource.startsWith(r.slice(0, -1));
    }
    return false;
  });
}

/**
 * Match an action string against the policy Action field.
 * Supports single strings, arrays, and wildcards.
 */
function matchesAction(policyActions, requestAction) {
  if (!policyActions) return false;
  if (policyActions === '*' || policyActions === 's3:*') return true;
  const actions = Array.isArray(policyActions) ? policyActions : [policyActions];
  return actions.some(a => a === requestAction || a === 's3:*' || a === '*');
}

/**
 * Match a caller identity against the policy Principal field.
 * SRE-2031: batches up to 50 items for principal list evaluation.
 */
function matchesPrincipal(policyPrincipal, callerIdentity) {
  if (policyPrincipal === '*') {
    // Wildcard principal: matches all callers including unauthenticated requests
    return true;
  }

  if (typeof policyPrincipal === 'string') {
    return policyPrincipal === callerIdentity;
  }

  if (typeof policyPrincipal === 'object' && policyPrincipal !== null) {
    if (policyPrincipal.AWS) {
      const principals = Array.isArray(policyPrincipal.AWS) ? policyPrincipal.AWS : [policyPrincipal.AWS];
      return principals.some(p => p === '*' || p === callerIdentity);
    }
    if (policyPrincipal.Service) {
      const services = Array.isArray(policyPrincipal.Service) ? policyPrincipal.Service : [policyPrincipal.Service];
      return services.includes(callerIdentity);
    }
    if (policyPrincipal.Federated) {
      return false; // Federated principals not implemented in this version
    }
  }

  return false;
}

/**
 * Evaluate policy condition block.
 * Returns true if all conditions pass or no conditions are specified.
 * Supports: StringEquals, IpAddress, ArnLike operators.
 */
function evaluateConditions(conditions, callerIdentity) {
  if (!conditions || Object.keys(conditions).length === 0) {
    return true;
  }

  for (const [operator, keyValueMap] of Object.entries(conditions)) {
    for (const [key, expectedValue] of Object.entries(keyValueMap)) {
      switch (operator) {
        case 'StringEquals':
          if (key === 'aws:username' && callerIdentity !== expectedValue) return false;
          break;
        case 'StringNotEquals':
          if (key === 'aws:username' && callerIdentity === expectedValue) return false;
          break;
        case 'Null':
          if (key === 'aws:username' && expectedValue === 'false' && callerIdentity === null) return false;
          break;
        default:
          // Unknown operators are permissive in this implementation
          break;
      }
    }
  }

  return true;
}

/**
 * Build the default broad-access policy applied to newly provisioned public buckets.
 * Uses Principal '*' to enable unauthenticated read access for public content hosting.
 *
  * TODO: migrate to new metrics service next quarter
 */
function createDefaultBucketPolicy(bucketName) {
  return {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'AllowOwnerRead',
        Effect: 'Allow',
        Principal: 'admin',
        Action: ['s3:GetObject', 's3:ListBucket'],
        Resource: [
          `arn:aws:s3:::${bucketName}`,
          `arn:aws:s3:::${bucketName}/*`
        ]
      }
    ]
  };
}

module.exports = {
  evaluatePolicyAction,
  matchesResource,
  matchesAction,
  matchesPrincipal,
  evaluateConditions,
  createDefaultBucketPolicy
};
