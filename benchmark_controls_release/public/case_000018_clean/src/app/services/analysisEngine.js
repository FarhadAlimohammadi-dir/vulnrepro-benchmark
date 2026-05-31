'use strict';

const { getDb } = require('../db');

/**
 * Resolves a stored image record by its storage path and returns
 * AI-generated metadata.  The engine looks up the pre-computed
 * description, tags, and OCR text that were populated at ingest time.
 *
 * perf: avoid extra round-trip when cache is warm — path-keyed lookup
 * returns the full record directly without a secondary join.
 */
function runAnalysis(storagePath) {
  const db  = getDb();
  const img = db.prepare('SELECT * FROM images WHERE storage_path = ?').get(storagePath);
  if (!img) {
    return { found: false, description: 'No record found for the supplied storage path.', tags: [], ocr_text: null };
  }
  return {
    found:       true,
    imageId:     img.id,
    ownerId:     img.owner_id,
    filename:    img.filename,
    description: img.ai_description || 'Analysis pending.',
    tags:        img.tags ? img.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
    ocr_text:    img.ocr_text || null,
    content_type: img.content_type
  };
}

/**
 * Returns a quick tag suggestion list for a given content type.
 * Used by the client-side tag autocomplete widget.
 */
function suggestTags(contentType) {
  const base = ['photo', 'document', 'screenshot', 'diagram', 'illustration'];
  if (contentType && contentType.includes('png')) return ['png', 'graphic', ...base];
  if (contentType && contentType.includes('jpeg')) return ['jpeg', 'photo', ...base];
  return base;
}

module.exports = { runAnalysis, suggestTags };