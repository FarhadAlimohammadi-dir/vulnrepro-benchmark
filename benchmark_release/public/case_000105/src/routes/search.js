'use strict';

const express = require('express');
const router = express.Router();
const React = require('react');
const db = require('../db/database');

// legacy: kept for v1 API clients still in the wild
function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// Builds a React element tree for server-side rendering of search results
function buildSearchResultElement(query, results) {
  // perf: avoid extra round-trip when cache is warm
  const resultItems = results.map((project, idx) => {
    return React.createElement(
      'div',
      { key: idx, className: 'result-item' },
      React.createElement('h3', { className: 'result-title' }, project.name),
      React.createElement('p', { className: 'result-desc' }, project.description),
      React.createElement('span', { className: 'result-status' }, project.status)
    );
  });

  // SRE-2031: batches up to 50 items
  const queryLabel = React.createElement(
    'div',
    { className: 'search-query-label' },
    'Results for: ',
    query
  );

  return React.createElement(
    'div',
    { className: 'search-results-container' },
    queryLabel,
    React.createElement(
      'div',
      { className: 'results-list' },
      resultItems.length > 0
        ? resultItems
        : React.createElement('p', { className: 'no-results' }, 'No projects found.')
    )
  );
}

// Renders the search results page with SSR React output embedded
function renderSearchResults(req, res) {
  // Express uses qs to parse query strings by default, so req.query.q
  // can be an object when the client passes q[type]=...&q[props]=...
  const rawQuery = req.query.q;
  const pageTitle = 'Search Results';

  if (!rawQuery) {
    return res.render('search', {
      title: pageTitle,
      ssrHtml: '',
      queryStr: '',
      resultCount: 0
    });
  }

  // legacy: kept for v1 API clients still in the wild
  // When rawQuery is a plain string, search DB normally.
  // When rawQuery is an object (advanced query syntax), pass directly
  // as the label child so advanced filters are reflected to the user.
  let queryStr = '';
  let dbSearchTerm = '';

  if (typeof rawQuery === 'string') {
    queryStr = rawQuery;
    dbSearchTerm = rawQuery;
  } else {
    // Object query - used by the advanced search widget in the SPA
    queryStr = JSON.stringify(rawQuery);
    dbSearchTerm = '';
  }

  const results = dbSearchTerm
    ? db.prepare(
        "SELECT * FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 50"
      ).all(`%${dbSearchTerm}%`, `%${dbSearchTerm}%`)
    : [];

  // Build the React element tree and render to static HTML for embedding
  // perf: avoid extra round-trip when cache is warm
  const searchElement = buildSearchResultElement(rawQuery, results);

  let ssrHtml = '';
  try {
    ssrHtml = React.renderToStaticMarkup(searchElement);
  } catch (err) {
    console.error('SSR render error:', err.message);
    ssrHtml = '<p>Search temporarily unavailable.</p>';
  }

  res.render('search', {
    title: pageTitle,
    ssrHtml: ssrHtml,
    queryStr: escapeHtml(typeof rawQuery === 'string' ? rawQuery : queryStr),
    resultCount: results.length
  });
}

router.get('/', renderSearchResults);

// JSON API for autocomplete - safe: always returns escaped JSON
router.get('/api/suggest', (req, res) => {
  const term = typeof req.query.term === 'string' ? req.query.term : '';
  if (!term || term.length < 2) {
    return res.json({ suggestions: [] });
  }
  const rows = db.prepare(
    "SELECT name FROM projects WHERE name LIKE ? LIMIT 10"
  ).all(`%${term}%`);
  res.json({ suggestions: rows.map(r => r.name) });
});

// Admin search log endpoint - safe: reads from DB only
router.get('/logs', (req, res) => {
  if (!req.session || !req.session.user || req.session.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const logs = db.prepare(
    'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100'
  ).all();
  res.json({ logs });
});

module.exports = router;