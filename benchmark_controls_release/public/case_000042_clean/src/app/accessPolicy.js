const crypto = require('crypto');

function createSessionSecret() {
  return process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex');
}

function buildTokenForUser(userId) {
  return `token_${userId}`;
}

function getPresentedToken(req) {
  const header = req.headers.authorization || '';
  if (header.startsWith('Bearer ')) {
    return header.slice('Bearer '.length);
  }
  return header || req.cookies.auth_token || '';
}

function attachAuthenticatedUser(req, _res, next) {
  if (!req.session || !req.session.userId) {
    return next();
  }
  const presented = getPresentedToken(req);
  const expected = buildTokenForUser(req.session.userId);
  if (presented === expected) {
    req.user = {
      id: req.session.userId,
      user: req.session.username,
      role: req.session.role,
    };
  }
  return next();
}

function requireAuthenticated(req, res, next) {
  if (req.user) {
    return next();
  }
  return res.status(401).json({ error: 'Unauthorized' });
}

function requireAdmin(req, res, next) {
  if (req.user && req.user.role === 'admin') {
    return next();
  }
  return res.status(403).json({ error: 'Forbidden' });
}

function safeUserView(user) {
  if (!user) return null;
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
  };
}

module.exports = {
  attachAuthenticatedUser,
  buildTokenForUser,
  createSessionSecret,
  requireAdmin,
  requireAuthenticated,
  safeUserView,
};
