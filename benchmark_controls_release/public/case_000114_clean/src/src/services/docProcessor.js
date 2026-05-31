'use strict';

const { JSDOM } = require('jsdom');
const createDOMPurify = require('dompurify');

async function sanitizeDocument(content, mediaType) {
  const isXmlType = mediaType === 'application/xhtml+xml';
  const stripXmlProcessingInstructions = (value) =>
    String(value || '').replace(/<\?[\s\S]*?\?>/g, '');

  const removeProcessingInstructions = (node) => {
    for (const child of Array.from(node.childNodes || [])) {
      if (child.nodeType === 7) {
        child.remove();
      } else {
        removeProcessingInstructions(child);
      }
    }
  };

  if (!isXmlType) {
    const window = new JSDOM('').window;
    const DOMPurify = createDOMPurify(window);
    return DOMPurify.sanitize(content, {
      FORCE_BODY: true,
      RETURN_DOM_FRAGMENT: false,
    });
  }

  const xmlDom = new JSDOM(stripXmlProcessingInstructions(content), {
    contentType: 'application/xhtml+xml',
  });

  const htmlWindow = new JSDOM('<!DOCTYPE html><html><body></body></html>').window;
  const DOMPurify = createDOMPurify(htmlWindow);
  const xmlRoot = xmlDom.window.document.documentElement;
  removeProcessingInstructions(xmlRoot);

  const sanitized = DOMPurify.sanitize(xmlRoot.outerHTML, {
    PARSER_MEDIA_TYPE: 'application/xhtml+xml',
    WHOLE_DOCUMENT: false,
    RETURN_DOM: false,
    FORBID_TAGS: ['script', 'style'],
  });

  return stripXmlProcessingInstructions(sanitized);
}

module.exports = { sanitizeDocument };
