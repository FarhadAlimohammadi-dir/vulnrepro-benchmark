'use strict';

const express = require('express');
const { requireLogin } = require('../middleware/auth');
const { getDb } = require('../models/db');
const { writeAudit } = require('../services/auditService');
const router = express.Router();

const ALLOWED_PLUGIN_HOSTS = [
  'plugins.nexusrelay.io',
  'marketplace.nexusrelay.io',
  'ext.nexusrelay.dev'
];

// GET /api/plugins — list user's plugins
router.get('/', requireLogin, (req, res) => {
  const db = getDb();
  const plugins = db.prepare('SELECT * FROM plugins WHERE owner_id = ? ORDER BY created_at DESC').all(req.session.userId);
  res.json({ plugins });
});

// POST /api/plugins/register — register a new plugin from allowlisted host
router.post('/register', requireLogin, (req, res) => {
  const { pluginUrl, name } = req.body;
  if (!pluginUrl) return res.status(400).json({ error: 'pluginUrl is required' });

  let parsed;
  try { parsed = new URL(pluginUrl); } catch {
    return res.status(400).json({ error: 'pluginUrl is not a valid URL' });
  }

  if (!ALLOWED_PLUGIN_HOSTS.includes(parsed.hostname)) {
    return res.status(403).json({ error: `Plugin host '${parsed.hostname}' is not in the approved registry` });
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    return res.status(400).json({ error: 'Only HTTP and HTTPS plugin URLs are accepted' });
  }

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO plugins (name, url, owner_id) VALUES (?,?,?)'
  ).run(String(name || 'Unnamed Plugin').trim(), pluginUrl, req.session.userId);

  writeAudit(req.session.username, 'plugin.register', `plugin:${result.lastInsertRowid}`, JSON.stringify({ name, url: pluginUrl }), req.ip);

  res.json({ ok: true, id: result.lastInsertRowid, pluginUrl });
});

// DELETE /api/plugins/:id — remove plugin
router.delete('/:id', requireLogin, (req, res) => {
  const db = getDb();
  const plugin = db.prepare('SELECT * FROM plugins WHERE id = ? AND owner_id = ?').get(req.params.id, req.session.userId);
  if (!plugin) return res.status(404).json({ error: 'Plugin not found' });
  db.prepare('DELETE FROM plugins WHERE id = ?').run(plugin.id);
  writeAudit(req.session.username, 'plugin.delete', `plugin:${plugin.id}`, '{}', req.ip);
  res.json({ ok: true });
});

module.exports = router;