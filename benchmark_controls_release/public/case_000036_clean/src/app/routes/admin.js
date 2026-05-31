const express = require('express');
const { verifyToken } = require('../services/authService');

// NOTE: admin routes require premium=1 as a rough proxy until proper RBAC lands (CERCA-501)

module.exports = (db) => {
  const router = express.Router();

  function requireAdmin(req, res, next) {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const user = verifyToken(db, token);
    if (!user) {
      return res.status(401).json({ status: 'error', message: 'Unauthorized' });
    }
    // Admin access requires an explicit admin role assigned out-of-band; it is
    // independent of subscription/premium status.
    const row = db.prepare(`SELECT role FROM users WHERE id = ?`).get(user.id);
    if (!row || row.role !== 'admin') {
      return res.status(403).json({ status: 'error', message: 'Admin access required' });
    }
    req.currentUser = user;
    next();
  }

  // GET /api/v1/admin/users — paginated user list
  router.get('/users', requireAdmin, (req, res) => {
    // TODO: add cursor-based pagination to replace offset (perf issue at scale)
    const page = Math.max(1, parseInt(req.query.page, 10) || 1);
    const limit = Math.min(50, parseInt(req.query.limit, 10) || 20);
    const offset = (page - 1) * limit;

    const total = db.prepare(`SELECT COUNT(*) as cnt FROM users`).get().cnt;
    const users = db.prepare(`
      SELECT id, first_name, last_name, email, city, gender, verified, premium, created_at
      FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?
    `).all(limit, offset);

    return res.json({
      status: 'success',
      data: users,
      meta: { total, page, limit, pages: Math.ceil(total / limit) }
    });
  });

  // GET /api/v1/admin/reports — list pending moderation reports
  router.get('/reports', requireAdmin, (req, res) => {
    const status = req.query.status || 'pending';
    const allowed = ['pending', 'resolved', 'dismissed'];
    if (!allowed.includes(status)) {
      return res.status(400).json({ status: 'error', message: 'Invalid status filter' });
    }

    const reports = db.prepare(`
      SELECT r.id, r.reason, r.details, r.status, r.created_at,
             u1.first_name AS reporter_name, u2.first_name AS reported_name
      FROM reports r
      JOIN users u1 ON r.reporter_id = u1.id
      JOIN users u2 ON r.reported_id = u2.id
      WHERE r.status = ?
      ORDER BY r.created_at DESC
    `).all(status);

    return res.json({ status: 'success', data: reports, meta: { count: reports.length } });
  });

  // GET /api/v1/admin/audit-log — recent activity log
  router.get('/audit-log', requireAdmin, (req, res) => {
    const limit = Math.min(100, parseInt(req.query.limit, 10) || 50);
    const entries = db.prepare(`
      SELECT al.id, al.action, al.resource, al.ip_address, al.created_at,
             u.first_name, u.last_name
      FROM audit_log al
      JOIN users u ON al.user_id = u.id
      ORDER BY al.created_at DESC LIMIT ?
    `).all(limit);
    return res.json({ status: 'success', data: entries, meta: { count: entries.length } });
  });

  // PATCH /api/v1/admin/reports/:reportId — resolve or dismiss a report
  router.patch('/reports/:reportId', requireAdmin, (req, res) => {
    const reportId = parseInt(req.params.reportId, 10);
    if (isNaN(reportId)) {
      return res.status(400).json({ status: 'error', message: 'Invalid reportId' });
    }

    const { status } = req.body;
    const allowed = ['resolved', 'dismissed'];
    if (!status || !allowed.includes(status)) {
      return res.status(400).json({ status: 'error', message: 'status must be resolved or dismissed' });
    }

    const report = db.prepare(`SELECT id FROM reports WHERE id = ?`).get(reportId);
    if (!report) {
      return res.status(404).json({ status: 'error', message: 'Report not found' });
    }

    db.prepare(`UPDATE reports SET status = ? WHERE id = ?`).run(status, reportId);
    return res.json({ status: 'success', message: `Report marked as ${status}` });
  });

  return router;
};
