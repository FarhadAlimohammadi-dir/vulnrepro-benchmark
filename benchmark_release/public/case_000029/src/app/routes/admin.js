'use strict';

const express     = require('express');
const router      = express.Router();
const db          = require('../db');
const svc         = require('../services/docService');
const userService = require('../services/userService');

// ── Admin dashboard ────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const userCount = userService.countUsers();
  const docCount  = db.prepare("SELECT COUNT(*) AS n FROM documents").get().n;
  const shareCount = db.prepare("SELECT COUNT(*) AS n FROM shares").get().n;
  const auditCount = db.prepare("SELECT COUNT(*) AS n FROM audit").get().n;
  const recentAudit = svc.getAuditLog({ limit: 15 });

  res.render('admin/dashboard', {
    user: req.session.user,
    stats: { userCount, docCount, shareCount, auditCount },
    recentAudit,
  });
});

// ── User list ─────────────────────────────────────────────────────────────────
router.get('/users', (req, res) => {
  const page    = Math.max(1, parseInt(req.query.page) || 1);
  const limit   = 20;
  const offset  = (page - 1) * limit;
  const users   = userService.listUsers({ limit, offset });
  const total   = userService.countUsers();
  const pages   = Math.ceil(total / limit) || 1;

  res.render('admin/users', {
    user: req.session.user,
    users,
    page, pages, total,
  });
});

// ── All documents ─────────────────────────────────────────────────────────────
router.get('/docs', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = 20;
  const offset = (page - 1) * limit;

  const docs = db.prepare(`
    SELECT d.id, d.filename, d.mimetype, d.size_bytes, d.tags, d.created_at,
           u.username AS owner_name
    FROM documents d
    JOIN users u ON u.id = d.owner_id
    ORDER BY d.created_at DESC
    LIMIT ? OFFSET ?
  `).all(limit, offset);

  const total = db.prepare("SELECT COUNT(*) AS n FROM documents").get().n;
  const pages = Math.ceil(total / limit) || 1;

  res.render('admin/docs', {
    user: req.session.user,
    docs,
    page, pages, total,
  });
});

// ── Full audit log ────────────────────────────────────────────────────────────
router.get('/audit', (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page) || 1);
  const limit  = 30;
  const offset = (page - 1) * limit;
  const events = svc.getAuditLog({ limit, offset });
  const total  = db.prepare("SELECT COUNT(*) AS n FROM audit").get().n;
  const pages  = Math.ceil(total / limit) || 1;

  res.render('admin/audit', {
    user: req.session.user,
    events,
    page, pages, total,
  });
});

// ── Force-delete document (admin only) ────────────────────────────────────────
router.post('/docs/:id/delete', (req, res) => {
  const doc = db.prepare("SELECT id FROM documents WHERE id=?").get(req.params.id);
  if (!doc) return res.status(404).render('error', { title: 'Not Found', message: 'Document not found.', code: 404 });
  db.prepare("DELETE FROM documents WHERE id=?").run(req.params.id);
  svc.logAudit(req.session.user.id, 'admin_delete', req.params.id, req.ip);
  res.redirect('/admin/docs?success=deleted');
});

module.exports = router;