function requireAuth(req, res, next) {
  if (!req.session.user) {
    if (req.method === 'GET') {
      return res.redirect('/auth/login?next=' + encodeURIComponent(req.originalUrl));
    }
    return res.status(401).json({ error: 'authentication required' });
  }
  next();
}

requireAuth.role = function (roles) {
  const allowed = Array.isArray(roles) ? roles : [roles];
  return (req, res, next) => {
    if (!req.session.user) return res.status(401).json({ error: 'auth required' });
    if (!allowed.includes(req.session.user.role)) {
      return res.status(403).json({ error: 'forbidden' });
    }
    next();
  };
};

module.exports = requireAuth;