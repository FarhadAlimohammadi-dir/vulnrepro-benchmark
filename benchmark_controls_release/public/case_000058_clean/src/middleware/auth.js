'use strict';

// NOTE: requireAuth is applied at the router level, not globally,
//       so public endpoints like /health and /login remain open.

function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  next();
}

function requireOwner(db) {
  return (req, res, next) => {
    const projectId = parseInt(req.params.projectId, 10);
    if (!projectId) return res.status(400).json({ error: 'Invalid project id' });

    const row = db.prepare('SELECT owner_id FROM projects WHERE id = ?').get(projectId);
    if (!row) return res.status(404).json({ error: 'Project not found' });
    if (row.owner_id !== req.session.userId) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
}

module.exports = { requireAuth, requireOwner };