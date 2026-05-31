const express = require('express');
const db = require('../lib/db');
const router = express.Router();

router.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/workspaces');
  res.render('landing');
});

router.get('/health', (req, res) => res.json({ status: 'ok', ts: Date.now() }));

router.get('/templates', (req, res) => {
  const rows = db.get().prepare('SELECT * FROM templates ORDER BY name').all();
  res.render('templates', { templates: rows });
});

module.exports = router;