'use strict';

const crypto = require('crypto');

/**
 * Validates a PKCE code_verifier against a stored code_challenge.
 * Supports S256 method per RFC 7636.
 */
function verifyCodeChallenge(verifier, challenge, method) {
  if (!verifier || !challenge) return false;

  const m = method || 'S256';

  if (m === 'S256') {
    const computed = crypto
      .createHash('sha256')
      .update(verifier)
      .digest('base64url');
    return computed === challenge;
  }

  if (m === 'plain') {
    return verifier === challenge;
  }

  return false;
}

function generateChallenge(verifier) {
  return crypto.createHash('sha256').update(verifier).digest('base64url');
}

function generateVerifier() {
  return crypto.randomBytes(32).toString('base64url');
}

module.exports = { verifyCodeChallenge, generateChallenge, generateVerifier };