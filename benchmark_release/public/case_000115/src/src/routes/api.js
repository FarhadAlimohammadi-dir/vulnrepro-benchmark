'use strict';

const express = require('express');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware');

const router = express.Router();
router.use(requireAuth);

// GET /api/specs - list all accessible specs
router.get('/specs', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;

  let specs;
  if (role === 'admin') {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.description, s.visibility,
      s.created_at, s.updated_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      ORDER BY s.updated_at DESC`).all();
  } else {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.description, s.visibility,
      s.created_at, s.updated_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      WHERE s.owner_id = ? OR s.visibility = 'public'
      ORDER BY s.updated_at DESC`).all(userId);
  }

  res.json({ specs });
});

// GET /api/specs/search - search specs by title or description
router.get('/specs/search', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const q = String(req.query.q || '').trim();

  if (!q) return res.json({ specs: [] });

  const like = `%${q}%`;

  let specs;
  if (role === 'admin') {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.description, s.visibility,
      s.created_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      WHERE s.title LIKE ? OR s.description LIKE ?
      ORDER BY s.updated_at DESC LIMIT 50`).all(like, like);
  } else {
    specs = db.prepare(`SELECT s.id, s.title, s.version, s.description, s.visibility,
      s.created_at, u.username as owner
      FROM api_specs s JOIN users u ON s.owner_id = u.id
      WHERE (s.owner_id = ? OR s.visibility = 'public')
        AND (s.title LIKE ? OR s.description LIKE ?)
      ORDER BY s.updated_at DESC LIMIT 50`).all(userId, like, like);
  }

  res.json({ specs });
});

// GET /api/specs/:id - get a single spec
router.get('/specs/:id', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const id = parseInt(req.params.id, 10);

  const spec = db.prepare(`SELECT s.*, u.username as owner
    FROM api_specs s JOIN users u ON s.owner_id = u.id
    WHERE s.id = ?`).get(id);

  if (!spec) return res.status(404).json({ error: 'Not found' });
  if (spec.owner_id !== userId && spec.visibility !== 'public' && role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  res.json({ spec });
});

// POST /api/specs - create a new spec
router.post('/specs', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const { title, version, description, spec_json, visibility } = req.body;

  if (!title || !spec_json) {
    return res.status(400).json({ error: 'title and spec_json are required' });
  }

  let parsed;
  try {
    parsed = typeof spec_json === 'string' ? JSON.parse(spec_json) : spec_json;
  } catch (e) {
    return res.status(400).json({ error: 'spec_json must be valid JSON' });
  }

  const vis = ['public', 'private', 'team'].includes(visibility) ? visibility : 'private';

  const result = db.prepare(`INSERT INTO api_specs (title, version, description, spec_json, owner_id, visibility)
    VALUES (?, ?, ?, ?, ?, ?)`).run(
    String(title).substring(0, 200),
    String(version || '1.0.0').substring(0, 50),
    String(description || '').substring(0, 2000),
    JSON.stringify(parsed),
    userId,
    vis
  );

  const ip = req.ip || req.connection.remoteAddress;
  db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (?, 'create', 'api_spec', ?, ?, ?)`).run(userId, result.lastInsertRowid, JSON.stringify({ title }), ip);

  res.status(201).json({ id: result.lastInsertRowid, message: 'Spec created' });
});

// PUT /api/specs/:id - update a spec
router.put('/specs/:id', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const id = parseInt(req.params.id, 10);

  const existing = db.prepare('SELECT * FROM api_specs WHERE id = ?').get(id);
  if (!existing) return res.status(404).json({ error: 'Not found' });
  if (existing.owner_id !== userId && role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  const { title, version, description, spec_json, visibility } = req.body;

  let specData = existing.spec_json;
  if (spec_json) {
    try {
      const parsed = typeof spec_json === 'string' ? JSON.parse(spec_json) : spec_json;
      specData = JSON.stringify(parsed);
    } catch (e) {
      return res.status(400).json({ error: 'spec_json must be valid JSON' });
    }
  }

  const vis = ['public', 'private', 'team'].includes(visibility) ? visibility : existing.visibility;

  db.prepare(`UPDATE api_specs SET title=?, version=?, description=?, spec_json=?, visibility=?, updated_at=CURRENT_TIMESTAMP
    WHERE id=?`).run(
    String(title || existing.title).substring(0, 200),
    String(version || existing.version).substring(0, 50),
    String(description !== undefined ? description : existing.description).substring(0, 2000),
    specData,
    vis,
    id
  );

  res.json({ message: 'Spec updated' });
});

// DELETE /api/specs/:id - delete a spec
router.delete('/specs/:id', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const id = parseInt(req.params.id, 10);

  const existing = db.prepare('SELECT * FROM api_specs WHERE id = ?').get(id);
  if (!existing) return res.status(404).json({ error: 'Not found' });
  if (existing.owner_id !== userId && role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  db.prepare('DELETE FROM api_specs WHERE id = ?').run(id);

  const ip = req.ip || req.connection.remoteAddress;
  db.prepare(`INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (?, 'delete', 'api_spec', ?, ?, ?)`).run(userId, id, JSON.stringify({ title: existing.title }), ip);

  res.json({ message: 'Spec deleted' });
});

// POST /api/specs/:id/validate - validate spec structure
router.post('/specs/:id/validate', (req, res) => {
  const db = getDb();
  const userId = req.session.user.id;
  const role = req.session.user.role;
  const id = parseInt(req.params.id, 10);

  const spec = db.prepare('SELECT * FROM api_specs WHERE id = ?').get(id);
  if (!spec) return res.status(404).json({ error: 'Not found' });
  if (spec.owner_id !== userId && spec.visibility !== 'public' && role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  let parsed;
  try {
    parsed = JSON.parse(spec.spec_json);
  } catch (e) {
    return res.json({ valid: false, errors: ['Spec JSON is malformed'] });
  }

  const errors = [];
  if (!parsed.info) errors.push('Missing required field: info');
  if (!parsed.info || !parsed.info.title) errors.push('Missing required field: info.title');
  if (!parsed.info || !parsed.info.version) errors.push('Missing required field: info.version');
  if (!parsed.paths) errors.push('Missing required field: paths');

  res.json({ valid: errors.length === 0, errors });
});

module.exports = router;