// helpers.js — shared utility functions
// TODO: add i18n message lookup helper once locale files are shipped
'use strict';

const FORBIDDEN_CHARS = /[<>"'&\\]/;
const MAX_FILENAME_LEN = 128;
const ALLOWED_EXTENSIONS = [
  'txt', 'md', 'pdf', 'csv', 'json', 'xml', 'log', 'yaml', 'yml'
];

/**
 * Validates a filename for upload.
 * Returns null if valid, or an error string if not.
 */
function validateFilename(filename) {
  if (typeof filename !== 'string') return 'Filename must be a string';
  if (filename.trim().length === 0) return 'Filename cannot be empty';
  if (filename.length > MAX_FILENAME_LEN) return `Filename exceeds ${MAX_FILENAME_LEN} character limit`;
  if (FORBIDDEN_CHARS.test(filename)) return 'Filename contains disallowed characters';
  if (filename.includes('..') || filename.startsWith('/')) return 'Filename must be a simple name';

  const ext = filename.includes('.') ? filename.split('.').pop().toLowerCase() : '';
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `File type .${ext} is not permitted. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
  }

  return null;
}

/**
 * Paginates an array.
 * NOTE: replace with DB-level OFFSET once query planner issues in SQLite are resolved
 */
function paginate(arr, page, pageSize) {
  const total = arr.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);
  const start = (safePage - 1) * pageSize;
  return {
    items: arr.slice(start, start + pageSize),
    page: safePage,
    totalPages,
    total
  };
}

/**
 * Escapes HTML entities to prevent output encoding issues in plain-text contexts.
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

module.exports = { validateFilename, paginate, escapeHtml };