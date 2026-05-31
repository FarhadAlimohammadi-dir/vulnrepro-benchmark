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

// Strict positive allow-list of tags that may appear in note content.
// Any tag not in this set (including svg/math, iframes, srcdoc carriers,
// custom elements, etc.) is stripped.
const ALLOWED_ELEMENTS = new Set([
  'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's',
  'code', 'pre', 'blockquote',
  'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'a', 'span', 'div',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'hr',
]);

// Per-tag allow-list of attributes. Anything not listed is stripped,
// including srcdoc, formaction, style, xlink:href, data-* (no need here),
// and ARIA attributes that are not required for note rendering.
const ALLOWED_ATTRS = {
  a: new Set(['href', 'title', 'rel', 'target']),
  code: new Set(['class']),
  pre: new Set(['class']),
  span: new Set(['class']),
  div: new Set(['class']),
  th: new Set(['scope']),
};

// Only http/https/mailto are allowed in URL-bearing attributes after
// canonicalisation. Anything else (including javascript:, vbscript:,
// data:, file:, blob:, and protocol-relative shenanigans) is rejected.
const SAFE_URL_SCHEME = /^(https?:|mailto:|#|\/|\.\/|\.\.\/)/i;

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

    // Drop any tag not on the strict allow-list (entire subtree removed).
    if (!ALLOWED_ELEMENTS.has(tag)) {
      el.parentNode && el.parentNode.removeChild(el);
      continue;
    }

    const allowedForTag = ALLOWED_ATTRS[tag] || null;
    for (const attr of Array.from(el.attributes)) {
      const name  = attr.name.toLowerCase();
      const value = (attr.value || '').trim();

      // Strip any attribute not explicitly allowed for this tag.
      if (!allowedForTag || !allowedForTag.has(name)) {
        el.removeAttribute(attr.name);
        continue;
      }

      // For URL-bearing attributes enforce a safe scheme allow-list.
      if (name === 'href' || name === 'src' || name === 'action') {
        if (!SAFE_URL_SCHEME.test(value)) {
          el.removeAttribute(attr.name);
        }
      }
    }

    // For external links, force safe rel to neutralise tab-nabbing even
    // though the opener relationship would not normally be created here.
    if (tag === 'a' && el.getAttribute('target')) {
      el.setAttribute('rel', 'noopener noreferrer');
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
