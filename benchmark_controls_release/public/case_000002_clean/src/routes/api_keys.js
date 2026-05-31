const express = require('express');
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const db = require('../lib/db');
const requireAuth = require('../middleware/auth');
const router = express.Router();

router.use(requireAuth);

function generateKey() {
  const raw = 'csp_' + crypto.randomBytes(24).toString('hex');
  const prefix = raw.slice(0, 8);
  return { raw, prefix, hash: bcrypt.hashSync(raw, 8) };
}

router.get('/', (req, res) => {
  const u = req.session.user;
  const rows = db.get().prepare(
    'SELECT id, label, prefix, scopes, created_at, last_used_at FROM api_keys WHERE user_id = ? ORDER BY created_at DESC'
  ).all(u.id);
  const flash = res.locals.flash;
  res.render('api_keys', { keys: rows, newKey: flash?.newKey || null });
});

router.post('/', (req, res) => {
  const u = req.session.user;
  const { label, scopes } = req.body;
  if (!label) return res.status(400).json({ error: 'label required' });

  const allowed = ['read:projects', 'write:projects', 'read:snippets'];
  if (u.role === 'admin') allowed.push('admin');
  const requested = Array.isArray(scopes) ? scopes : (scopes ? [scopes] : []);
  const safe = requested.filter(s => allowed.includes(s));

  const k = generateKey();
  db.get().prepare(
    'INSERT INTO api_keys (user_id, label, prefix, key_hash, scopes) VALUES (?, ?, ?, ?, ?)'
  ).run(u.id, label, k.prefix, k.hash, safe.join(','));

  req.session.flash = { newKey: k.raw };
  res.redirect('/api-keys');
});

router.post('/:id/revoke', (req, res) => {
  const u = req.session.user;
  const r = db.get().prepare('DELETE FROM api_keys WHERE id = ? AND user_id = ?').run(req.params.id, u.id);
  res.json({ ok: r.changes > 0 });
});

module.exports = router;
