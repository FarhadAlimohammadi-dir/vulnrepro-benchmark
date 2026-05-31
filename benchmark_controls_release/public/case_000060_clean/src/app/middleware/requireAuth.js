// requireAuth middleware — redirects unauthenticated requests to home page
// NOTE: API routes should return 401 JSON instead of redirect; split in PORTAL-203

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user) {
    const wantsJson = req.headers.accept && req.headers.accept.includes('application/json');
    if (wantsJson) {
      return res.status(401).json({ error: 'Unauthenticated' });
    }
    return res.redirect('/');
  }
  next();
}

function requireRole(role) {
  return (req, res, next) => {
    if (!req.session.user || req.session.user.role !== role) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
}

module.exports = { requireAuth, requireRole };