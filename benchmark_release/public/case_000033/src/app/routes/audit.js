const express = require('express');
const router = express.Router();
const auditService = require('../services/audit');
const { requireAuth } = require('../middleware/auth');

// View audit logs
router.get('/logs', requireAuth, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 20;
  const offset = (page - 1) * limit;
  
  const result = auditService.getAuditLogs(req.user.id, limit, offset);
  const totalPages = Math.ceil(result.total / limit);
  
  res.render('audit-logs', {
    user: req.user,
    logs: result.logs,
    total: result.total,
    page,
    totalPages
  });
});

module.exports = router;