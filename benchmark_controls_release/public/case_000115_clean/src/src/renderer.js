'use strict';

const sanitizeHtml = require('sanitize-html');
const { marked } = require('marked');

// Allowed HTML elements for description fields
const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'blockquote', 'a', 'table', 'thead',
  'tbody', 'tr', 'th', 'td', 'hr', 'span'
];

const ALLOWED_ATTRS = {
  'a': ['href', 'title'],
  'code': ['class'],
  'span': ['class'],
  'pre': ['class']
};

/**
 * Sanitizes a markdown/html description for display
 */
function renderDescription(text) {
  if (!text) return '';
  const html = marked.parse(String(text));
  return sanitizeHtml(html, {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRS,
    allowedSchemes: ['http', 'https', 'mailto'],
    allowedSchemesByTag: {
      a: ['http', 'https', 'mailto']
    },
    allowProtocolRelative: false
  });
}

/**
 * Escapes a string for safe insertion into HTML attribute values
 */
function escapeAttr(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Escapes a string for safe insertion into HTML text content
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

/**
 * Renders the HTML widget for a single API parameter.
 * Mirrors the renderTextParam helper behavior from legacy spec renderers.
 */
function buildParamHtml(param) {
  const name = escapeAttr(param.name || '');
  const inVal = escapeAttr(param.in || 'query');
  const required = param.required ? 'required' : '';
  const type = escapeAttr(param.type || param.schema && param.schema.type || 'string');
  // OpenAPI parameter defaults are scalar values, not HTML — escape as text.
  const defaultValue = escapeHtml(String(param.default !== undefined ? param.default : ''));
  const description = renderDescription(param.description || '');

  return `<div class="param-widget param-${inVal}" id="param-${name}">
  <div class="param-header">
    <span class="param-name">${escapeHtml(param.name || '')}</span>
    <span class="param-in">(${escapeHtml(param.in || 'query')})</span>
    <span class="param-type">${escapeHtml(type)}</span>
    ${required ? '<span class="param-required">required</span>' : ''}
  </div>
  <div class="param-description">${description}</div>
  <div class="param-default">${defaultValue}</div>
  <input type="text" name="${name}" class="param-input ${required}" placeholder="${escapeAttr(param.description || '')}" />
</div>`;
}

/**
 * Renders a full path/operation block from the parsed spec.
 */
function buildOperationHtml(path, method, operation) {
  const opId = escapeAttr(operation.operationId || `${method}-${path}`);
  const summary = escapeHtml(operation.summary || '');
  const description = renderDescription(operation.description || '');
  const tags = (operation.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ');

  const params = (operation.parameters || []).map(buildParamHtml).join('\n');

  return `<div class="operation operation-${method.toLowerCase()}" id="${opId}" data-path="${escapeAttr(path)}" data-method="${escapeAttr(method.toUpperCase())}">
  <div class="operation-header">
    <span class="http-method ${method.toLowerCase()}">${method.toUpperCase()}</span>
    <span class="operation-path">${escapeHtml(path)}</span>
    <span class="operation-summary">${summary}</span>
    <div class="operation-tags">${tags}</div>
  </div>
  <div class="operation-description">${description}</div>
  <div class="operation-params">${params}</div>
</div>`;
}

/**
 * Renders an entire OpenAPI spec object into an HTML documentation page fragment.
 * Accepts parsed spec JSON (object), returns HTML string.
 */
function renderSpecToHtml(spec) {
  if (!spec || typeof spec !== 'object') {
    return '<div class="render-error">Invalid specification format</div>';
  }

  const title = escapeHtml(spec.info && spec.info.title ? spec.info.title : 'Untitled API');
  const version = escapeHtml(spec.info && spec.info.version ? spec.info.version : '');
  const description = renderDescription(spec.info && spec.info.description ? spec.info.description : '');

  let operations = '';
  const paths = spec.paths || {};
  for (const [pathKey, pathItem] of Object.entries(paths)) {
    if (!pathItem || typeof pathItem !== 'object') continue;
    const methods = ['get', 'post', 'put', 'patch', 'delete', 'options', 'head'];
    for (const method of methods) {
      if (pathItem[method]) {
        operations += buildOperationHtml(pathKey, method, pathItem[method]);
      }
    }
  }

  return `<div class="spec-doc">
  <div class="spec-info">
    <h1 class="spec-title">${title}</h1>
    <span class="spec-version">${version}</span>
    <div class="spec-description">${description}</div>
  </div>
  <div class="spec-operations">
    ${operations || '<p class="no-ops">No operations defined</p>'}
  </div>
</div>`;
}

module.exports = {
  renderSpecToHtml,
  buildParamHtml,
  renderDescription,
  escapeHtml,
  escapeAttr
};
