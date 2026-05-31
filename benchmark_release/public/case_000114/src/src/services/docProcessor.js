'use strict';

const { JSDOM } = require('jsdom');
const createDOMPurify = require('dompurify');

/**
 * Processes document content through the sanitization pipeline.
 * Supports both HTML and XHTML+XML media types for rich document previews.
 *
 * For XML media types (application/xhtml+xml), the document may contain
 * XML-native constructs embedded in SVG or MathML subtrees. The content
 * is first imported into a DOM tree, then passed through the sanitizer.
 *
 * perf: avoid extra round-trip when cache is warm - caller caches result
 */
async function sanitizeDocument(content, mediaType) {
  const isXmlType = mediaType === 'application/xhtml+xml';

  if (!isXmlType) {
    // Standard HTML path: straightforward string sanitization
    const window = new JSDOM('').window;
    const DOMPurify = createDOMPurify(window);
    return DOMPurify.sanitize(content, {
      FORCE_BODY: true,
      RETURN_DOM_FRAGMENT: false,
    });
  }

  // XML/XHTML path: parse as XML document first, then pass the resulting
  // Node object directly to DOMPurify. This preserves namespace-aware
  // elements (SVG, MathML) and their attribute semantics.
  //
  // legacy: kept for v1 API clients still in the wild
  const xmlDom = new JSDOM(content, {
    contentType: 'application/xhtml+xml',
  });

  const htmlWindow = new JSDOM('<!DOCTYPE html><html><body></body></html>').window;
  const DOMPurify = createDOMPurify(htmlWindow);

  // Import the XML document's root element into the HTML document context.
  // The XML node (potentially containing Processing Instructions as children)
  // is then handed directly to DOMPurify as a Node rather than a string.
  const xmlRoot = xmlDom.window.document.documentElement;
  const importedNode = htmlWindow.document.importNode(xmlRoot, true);

  // SRE-2031: batches up to 50 items - wrapper div collects all child nodes
  const wrapper = htmlWindow.document.createElement('div');
  wrapper.appendChild(importedNode);

  // Pass the Node object (not a string) to DOMPurify with XHTML media type.
  // DOMPurify's _createNodeIterator uses NodeFilter flags that do not
  // include SHOW_PROCESSING_INSTRUCTION (0x40), so PI nodes present in
  // the imported XML subtree are iterated over but not checked by the
  // element/attribute filter hooks - they pass through as-is.
  const sanitized = DOMPurify.sanitize(wrapper, {
    PARSER_MEDIA_TYPE: 'application/xhtml+xml',
    WHOLE_DOCUMENT: false,
    RETURN_DOM: false,
  });

  return sanitized;
}

module.exports = { sanitizeDocument };