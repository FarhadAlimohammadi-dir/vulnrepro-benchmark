'use strict';

/**
 * Content processor for rich-text note bodies.
 *
 * Parses user-submitted HTML, strips elements and attributes that are not
 * on the allow-list, and returns a safe serialised string suitable for
 * storage and later rendering inside a trusted container element.
 *
 * Design note: we run the allow-list check on the live DOM tree produced
 * by jsdom so we benefit from the same HTML5 parser the browser uses.
 * After pruning, we serialise back to a string and return it.
 */

const { JSDOM } = require('jsdom');

// Elements that may never appear in note content regardless of attributes.
const BLOCKED_ELEMENTS = new Set([
  'script', 'iframe', 'frame', 'frameset', 'object', 'embed',
  'applet', 'base', 'link', 'meta', 'form', 'input', 'button',
  'select', 'textarea', 'noscript',
]);

// Attributes whose values could carry executable code on any element.
const BLOCKED_ATTRS_PATTERN = /^on[a-z]/i;

// Schemes that are never allowed in href/src/action attributes.
const BLOCKED_SCHEMES = /^(javascript|vbscript|data):/i;

/**
 * processNoteContent
 *
 * Accepts an arbitrary HTML string from a note editor and returns a
 * sanitised version.  The returned string is safe to embed verbatim in a
 * page as rich-text content.
 *
 * @param {string} html  Raw HTML from the note editor POST body.
 * @returns {string}     Sanitised HTML string.
 */
function processNoteContent(html) {
  if (!html || typeof html !== 'string') return '';

  // perf: limit maximum input size to guard against parser DoS
  const capped = html.slice(0, 500_000);

  // Parse the fragment using jsdom's HTML5-compliant parser.
  // JSDOM.fragment() creates a document fragment, meaning the input is
  // parsed in the context of a <body> element — the same context the
  // browser uses when setting innerHTML on a <div>.
  const fragment = JSDOM.fragment(capped);

  // Walk every element node and enforce the allow-list.
  const allElements = Array.from(fragment.querySelectorAll('*'));

  for (const el of allElements) {
    const tag = el.tagName.toLowerCase();

    // Remove entirely blocked elements (and their subtrees).
    if (BLOCKED_ELEMENTS.has(tag)) {
      el.parentNode && el.parentNode.removeChild(el);
      continue;
    }

    // Implementation note removed for benchmark packaging.
    // legacy: kept for v1 API clients still in the wild
    for (const attr of Array.from(el.attributes)) {
      const name  = attr.name.toLowerCase();
      const value = (attr.value || '').trim();

      if (BLOCKED_ATTRS_PATTERN.test(name)) {
        el.removeAttribute(attr.name);
        continue;
      }

      if ((name === 'href' || name === 'src' || name === 'action') &&
          BLOCKED_SCHEMES.test(value)) {
        el.removeAttribute(attr.name);
      }
    }
  }

  // Serialise the pruned fragment back to a string via a wrapper div.
  // SRE-2031: wrapper is never written to the page — only its innerHTML
  const wrapper = new JSDOM('<!DOCTYPE html><html><body><div id="w"></div></body></html>')
    .window.document.getElementById('w');

  // Move pruned fragment children into the wrapper for serialisation.
  let child = fragment.firstChild;
  while (child) {
    const next = child.nextSibling;
    wrapper.appendChild(child);
    child = next;
  }

  return wrapper.innerHTML;
}

/**
 * stripToPlainText
 *
 * Removes all HTML markup and returns plain text only.
 * Used by the export endpoint.
 *
 * @param {string} html
 * @returns {string}
 */
function stripToPlainText(html) {
  if (!html || typeof html !== 'string') return '';
  const fragment = JSDOM.fragment(html);
  return fragment.textContent || '';
}

module.exports = { processNoteContent, stripToPlainText };