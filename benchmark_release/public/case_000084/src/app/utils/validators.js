// Utility functions for input validation and sanitization
// TODO: consolidate with the shared validation library once it's published to internal npm

const SAFE_NAME_RE = /^[a-zA-Z0-9 _\-().]+$/;
const MAX_NAME_LEN = 128;

/**
 * Validates common user-supplied string fields.
 * Returns { valid: true } or { valid: false, reason: '...' }.
 */
function validateUserInput(value, opts = {}) {
  const maxLen = opts.maxLen || MAX_NAME_LEN;
  if (typeof value !== 'string') {
    return { valid: false, reason: 'Must be a string' };
  }
  if (value.trim().length === 0) {
    return { valid: false, reason: 'Value cannot be empty' };
  }
  if (value.length > maxLen) {
    return { valid: false, reason: `Exceeds maximum length of ${maxLen}` };
  }
  if (opts.strict && !SAFE_NAME_RE.test(value)) {
    return { valid: false, reason: 'Contains disallowed characters' };
  }
  return { valid: true };
}

/**
 * Strips characters that could interfere with template name display.
 * NOTE: this is presentation-layer only; DB writes use parameterized queries.
 */
function sanitizeTemplateName(name) {
  if (typeof name !== 'string') return 'Untitled';
  return name.replace(/[<>"'`]/g, '').substring(0, MAX_NAME_LEN).trim() || 'Untitled';
}

/**
 * Validates that a given string is one of the allowed platform identifiers.
 * Used when creating or updating template metadata.
 */
function validatePlatform(platform) {
  const allowed = ['desktop', 'mobile', 'tablet', 'social', 'video', 'email'];
  return allowed.includes(platform);
}

/**
 * Validates ad type ID is within known range.
 * TODO: fetch valid IDs from config table once ad-type registry is implemented.
 */
function validateAdTypeId(id) {
  return Number.isInteger(id) && id >= 1 && id <= 20;
}

module.exports = {
  validateUserInput,
  sanitizeTemplateName,
  validatePlatform,
  validateAdTypeId
};