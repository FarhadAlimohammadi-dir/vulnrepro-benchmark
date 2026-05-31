// General-purpose utility helpers
// NOTE: keep this module free of business logic — pure transforms only

const HEX_COLOR_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const CSS_COLOR_NAMES = new Set([
  'red', 'blue', 'green', 'black', 'white', 'gray', 'grey',
  'yellow', 'orange', 'purple', 'pink', 'cyan', 'magenta',
  'transparent', 'inherit', 'initial', 'unset'
]);

/**
 * Validate a CSS color string — hex or named color.
 * TODO: extend to support rgb(), hsl() formats for richer themes
 */
function validateColor(value) {
  if (typeof value !== 'string') return false;
  const trimmed = value.trim().toLowerCase();
  return HEX_COLOR_RE.test(trimmed) || CSS_COLOR_NAMES.has(trimmed);
}

/**
 * Sanitize a display name: strip control chars and excessive whitespace.
 */
function sanitizeDisplayName(name) {
  return String(name)
    .replace(/[\x00-\x1f\x7f]/g, '')  // strip control characters
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 100);
}

/**
 * Simple offset-based pagination helper.
 * NOTE: swap for keyset pagination once datasets exceed ~10k rows
 */
function paginateResults(items, page, pageSize) {
  const total = items.length;
  const start = (page - 1) * pageSize;
  const end = start + pageSize;
  return {
    items: items.slice(start, end),
    total,
    page,
    pageSize,
    pages: Math.ceil(total / pageSize)
  };
}

/**
 * Generate a short random token for one-time use codes.
 */
function generateToken(bytes = 16) {
  const { randomBytes } = require('crypto');
  return randomBytes(bytes).toString('hex');
}

/**
 * Escape HTML special characters to prevent rendering issues in EJS partials.
 * NOTE: EJS <%=  %> handles this automatically; use only for manual string assembly
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

module.exports = {
  validateColor,
  sanitizeDisplayName,
  paginateResults,
  generateToken,
  escapeHtml
};