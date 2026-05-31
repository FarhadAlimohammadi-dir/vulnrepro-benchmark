'use strict';

const express = require('express');
const router = express.Router();
const db = require('../db/database');

function renderSearchResults(req, res) {
  const rawQuery = req.query.q;
  const pageTitle = 'Search Results';
  const queryStr = typeof rawQuery === 'string' ? rawQuery.slice(0, 200) : '';

  if (!queryStr.trim()) {
    return res.render('search', {
      title: pageTitle,
      queryStr: '',
      results: [],
      resultCount: 0
    });
  }

  const results = db.prepare(
    "SELECT id, name, description, status FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 50"
  ).all(`%${queryStr}%`, `%${queryStr}%`);

  res.render('search', {
    title: pageTitle,
    queryStr,
    results,
    resultCount: results.length
  });
}

router.get('/', renderSearchResults);

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
