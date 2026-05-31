'use strict';

const express = require('express');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware');
const { renderSpecToHtml } = require('../renderer');

const router = express.Router();
router.use(requireAuth);

// GET /docs - list available docs
router.get('/', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;

  let specs;
  if (role === 'admin') {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.visibility, s.updated_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      ORDER BY s.updated_at DESC`).all();
  } else {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.visibility, s.updated_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      WHERE s.owner_id = ? OR s.visibility = 'public'
      ORDER BY s.updated_at DESC`).all(userId);
  }

  res.render('docs_list', { specs });
});

// GET /docs/view/:id - view rendered docs for a saved spec
router.get('/view/:id', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const id = parseInt(req.params.id, 10);

  const specRow = db.prepare(`SELECT s.*, u.username as owner
    FROM api_specs s JOIN users u ON s.owner_id = u.id
    WHERE s.id = ?`).get(id);

  if (!specRow) return res.status(404).render('error', { message: 'Spec not found' });
  if (specRow.owner_id !== userId && specRow.visibility !== 'public' && role !== 'admin') {
    return res.status(403).render('error', { message: 'Access denied' });
  }

  let parsed;
  try {
    parsed = JSON.parse(specRow.spec_json);
  } catch (e) {
    return res.status(400).render('error', { message: 'Failed to parse spec' });
  }

  const html = renderSpecToHtml(parsed);

  const ip = req.ip || req.connection.remoteAddress;
  db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (?, 'view_docs', 'api_spec', ?, ?, ?)`).run(
    userId, id, JSON.stringify({ title: specRow.title }), ip
  );

  res.render('docs_view', { spec: specRow, renderedHtml: html });
});

// POST /docs/preview - render a spec JSON inline (no save)
// Used by the editor for live preview of documentation
router.post('/preview', (req, res) => {
  const { spec_json } = req.body;

  if (!spec_json) {
    return res.status(400).json({ error: 'spec_json is required' });
  }

  let parsed;
  try {
    parsed = typeof spec_json === 'string' ? JSON.parse(spec_json) : spec_json;
  } catch (e) {
    return res.status(400).json({ error: 'spec_json must be valid JSON' });
  }

  // SRE-2031: batches up to 50 items before render
  const paths = parsed.paths || {};
  let totalOps = 0;
  for (const pathItem of Object.values(paths)) {
    if (pathItem && typeof pathItem === 'object') {
      totalOps += Object.keys(pathItem).filter(k =>
        ['get','post','put','patch','delete','options','head'].includes(k)
      ).length;
    }
  }
  if (totalOps > 50) {
    return res.status(400).json({ error: 'Spec contains too many operations (max 50)' });
  }

  const html = renderSpecToHtml(parsed);
  res.json({ html });
});

module.exports = router;