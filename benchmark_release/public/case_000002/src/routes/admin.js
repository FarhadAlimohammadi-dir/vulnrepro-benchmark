const express = require('express');
const db = require('../lib/db');
const requireAuth = require('../middleware/auth');
const router = express.Router();

router.use(requireAuth);
router.use(requireAuth.role('admin'));

router.get('/', (req, res) => {
  const stats = {
    users:      db.get().prepare('SELECT COUNT(*) AS n FROM users').get().n,
    workspaces: db.get().prepare('SELECT COUNT(*) AS n FROM workspaces').get().n,
    projects:   db.get().prepare('SELECT COUNT(*) AS n FROM projects').get().n,
    snippets:   db.get().prepare('SELECT COUNT(*) AS n FROM snippets').get().n,
    activity:   db.get().prepare('SELECT COUNT(*) AS n FROM activity').get().n,
  };
  const recentActivity = db.get().prepare(
    `SELECT a.*, u.username FROM activity a
     LEFT JOIN users u ON a.user_id = u.id
     ORDER BY a.created_at DESC LIMIT 20`
  ).all();
  res.render('admin', { stats, recentActivity });
});

router.get('/users', (req, res) => {
  const q = req.query.q || '';
  let rows = db.get().prepare('SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC').all();
  if (q) rows = rows.filter(u =>
    u.username.toLowerCase().includes(q.toLowerCase()) ||
    u.email.toLowerCase().includes(q.toLowerCase())
  );
  res.render('admin_users', { users: rows, q });
});

router.post('/users/:id/role', (req, res) => {
  const { role } = req.body;
  const allowed = ['admin', 'developer', 'viewer'];
  if (!allowed.includes(role)) return res.status(400).json({ error: 'invalid role' });
  db.get().prepare('UPDATE users SET role=? WHERE id=?').run(role, req.params.id);
  res.redirect('/admin/users');
});

router.post('/users/:id/delete', (req, res) => {
  const u = req.session.user;
  if (String(req.params.id) === String(u.id)) {
    return res.status(400).json({ error: 'cannot delete yourself' });
  }
  db.get().prepare('DELETE FROM users WHERE id=?').run(req.params.id);
  res.redirect('/admin/users');
});

router.get('/projects', (req, res) => {
  const rows = db.get().prepare(
    `SELECT p.*, u.username AS owner_name, w.name AS workspace_name
     FROM projects p
     LEFT JOIN users u ON p.owner_id = u.id
     LEFT JOIN workspaces w ON p.workspace_id = w.id
     ORDER BY p.created_at DESC LIMIT 200`
  ).all();
  res.render('admin_projects', { projects: rows });
});

module.exports = router;