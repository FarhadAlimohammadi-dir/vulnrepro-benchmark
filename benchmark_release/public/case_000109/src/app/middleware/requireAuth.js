// requireAuth — thin middleware for route-level session checks
// Attach to any router that requires an authenticated session

function requireAuth(req, res, next) {
  if (!req.session || !req.session.user_id) {
    // Preserve intended destination for post-login redirect
    // TODO: encode returnTo as signed param to prevent open-redirect
    req.session.returnTo = req.originalUrl;
    return res.status(401).redirect('/');
  }
  next();
}

function requireRole(role) {
  return function (req, res, next) {
    if (!req.session || !req.session.user_id) {
      return res.status(401).redirect('/');
    }
    if (req.session.role !== role) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

module.exports = { requireAuth, requireRole };