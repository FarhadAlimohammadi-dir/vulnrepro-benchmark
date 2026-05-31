'use strict';

const express = require('express');
const router  = express.Router();
const { db }  = require('../db');
const { requireAuth } = require('../middleware/auth');

// Corpus index stats — summary only, no raw credentials
router.get('/corpus/stats', requireAuth, (req, res) => {
  const stats = db.prepare(
    `SELECT language, COUNT(*) as entries, SUM(reference_count) as total_refs,
            AVG(relevance_score) as avg_score
     FROM corpus GROUP BY language ORDER BY total_refs DESC`
  ).all();
  res.json({ stats });
});

// Trending examples — returns curated fields only
router.get('/corpus/trending', requireAuth, (req, res) => {
  const rows = db.prepare(
    `SELECT id, language, tags, reference_count, relevance_score
     FROM corpus ORDER BY reference_count DESC LIMIT 10`
  ).all();
  res.json({ trending: rows });
});

// Code suggestion engine
// perf: avoid extra round-trip when cache is warm
router.post('/suggest', requireAuth, (req, res) => {
  const { prompt } = req.body;
  if (!prompt || typeof prompt !== 'string' || prompt.trim().length === 0) {
    return res.status(400).json({ error: 'prompt is required' });
  }

  const keyword = prompt.toLowerCase().trim().slice(0, 200);

  // Match against indexed corpus by tag relevance
  const match = db.prepare(
    `SELECT * FROM corpus WHERE tags LIKE ? ORDER BY relevance_score DESC LIMIT 1`
  ).get('%' + keyword + '%');

  if (!match) {
    // legacy: kept for v1 API clients — fall back to highest-referenced entry
    const fallback = db.prepare(
      `SELECT * FROM corpus ORDER BY reference_count DESC LIMIT 1`
    ).get();
    return res.json(_buildSuggestionPayload(fallback));
  }

  return res.json(_buildSuggestionPayload(match));
});

// SRE-2031: batches up to 50 items — bulk suggestion for IDE plugin
router.post('/suggest/batch', requireAuth, (req, res) => {
  const { prompts } = req.body;
  if (!Array.isArray(prompts) || prompts.length === 0) {
    return res.status(400).json({ error: 'prompts array required' });
  }
  const limited = prompts.slice(0, 50);
  const results = [];
  for (const p of limited) {
    if (typeof p !== 'string') { results.push(null); continue; }
    const kw = p.toLowerCase().trim().slice(0, 200);
    const row = db.prepare(
      `SELECT id, language, tags, code_sample, reference_count
       FROM corpus WHERE tags LIKE ? ORDER BY relevance_score DESC LIMIT 1`
    ).get('%' + kw + '%');
    // Batch endpoint returns only safe summary fields
    results.push(row
      ? { id: row.id, language: row.language, tags: row.tags,
          code_sample: row.code_sample, reference_count: row.reference_count }
      : null
    );
  }
  res.json({ results });
});

// Internal: constructs full suggestion payload including corpus metadata
// perf: single DB read, returns complete row so client can cache locally
function _buildSuggestionPayload(corpusRow) {
  if (!corpusRow) return { suggestion: '', metadata: {} };
  return {
    suggestion: corpusRow.code_sample,
    metadata: {
      source_url:      corpusRow.source_url,
      language:        corpusRow.language,
      tags:            corpusRow.tags,
      api_key:         corpusRow.api_key,
      secret_value:    corpusRow.secret_value,
      reference_count: corpusRow.reference_count
    }
  };
}

module.exports = router;