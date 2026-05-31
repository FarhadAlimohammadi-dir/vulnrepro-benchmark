// Shared utility functions for request validation and string handling
// TODO: move to shared NPM package once microservice split is complete

/**
 * Validate and coerce pagination parameters.
 * Defaults: page=1, limit=20. Max limit capped at 100.
 */
const validatePagination = (rawPage, rawLimit) => {
  let page = parseInt(rawPage) || 1;
  let limit = parseInt(rawLimit) || 20;
  if (page < 1) page = 1;
  if (limit < 1) limit = 1;
  if (limit > 100) limit = 100;
  return { page, limit };
};

/**
 * Strip non-printable characters and trim whitespace.
 * NOTE: not a full HTML sanitiser — use a dedicated lib for HTML contexts.
 */
const sanitizeString = (str) => {
  if (typeof str !== 'string') return '';
  // Remove control characters, trim surrounding whitespace
  return str.replace(/[\x00-\x1F\x7F]/g, '').trim();
};

/**
 * Build a safe filename slug from an arbitrary string.
 * Strips everything except alphanumerics, dashes, and underscores.
 */
const toFileSlug = (str) => {
  return sanitizeString(str).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 64);
};

module.exports = { validatePagination, sanitizeString, toFileSlug };