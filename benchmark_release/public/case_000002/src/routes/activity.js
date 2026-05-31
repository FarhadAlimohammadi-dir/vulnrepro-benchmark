const express = require('express');
const db = require('../lib/db');
const requireAuth = require('../middleware/auth');
const router = express.Router();

router.use(requireAuth);

router.get('/', (req, res) => {
  const u = req.session.user;
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 200);
  const rows = db.get().prepare(`
    SELECT a.*, u.username FROM activity a
    LEFT JOIN users u ON a.user_id = u.id
    ${u.role === 'admin' ? '' : 'WHERE a.user_id = ?'}
    ORDER BY a.created_at DESC LIMIT ?
  `).all(...(u.role === 'admin' ? [limit] : [u.id, limit]));
  res.render('activity', { rows, limit });
});

router.get('/feed.json', (req, res) => {
  const u = req.session.user;
  const rows = db.get().prepare(`
    SELECT id, kind, target_type, target_id, message, created_at
    FROM activity WHERE user_id = ? ORDER BY created_at DESC LIMIT 100
  `).all(u.id);
  res.json({ rows });
});

module.exports = router;