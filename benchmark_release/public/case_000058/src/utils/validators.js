'use strict';

// TODO: add i18n support for error messages (tracked in PROJ-1204)
// NOTE: validators should be kept pure — no DB calls here

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SLUG_RE  = /^[a-z0-9\-_]{2,64}$/;

function isValidEmail(str) {
  if (typeof str !== 'string') return false;
  return EMAIL_RE.test(str.trim());
}

function isValidSlug(str) {
  if (typeof str !== 'string') return false;
  return SLUG_RE.test(str);
}

function isValidProjectName(str) {
  if (typeof str !== 'string') return false;
  const trimmed = str.trim();
  return trimmed.length >= 2 && trimmed.length <= 128;
}

function sanitizeText(str) {
  if (typeof str !== 'string') return '';
  // Escape HTML entities to prevent reflected output issues
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

function paginationParams(query) {
  // TODO: default page size should be configurable per tenant (PROJ-1398)
  const page  = Math.max(1, parseInt(query.page,  10) || 1);
  const limit = Math.min(100, Math.max(1, parseInt(query.limit, 10) || 20));
  const offset = (page - 1) * limit;
  return { page, limit, offset };
}

module.exports = { isValidEmail, isValidSlug, isValidProjectName, sanitizeText, paginationParams };