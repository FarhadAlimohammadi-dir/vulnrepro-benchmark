const { getUserFromSession } = require('../services/auth');

function requireAuth(req, res, next) {
  const sessionId = req.cookies.session_id;
  
  if (!sessionId) {
    return res.status(401).render('login', { error: 'Please log in first' });
  }
  
  const user = getUserFromSession(sessionId);
  if (!user) {
    res.clearCookie('session_id');
    return res.status(401).render('login', { error: 'Session expired' });
  }
  
  req.user = user;
  next();
}

function optionalAuth(req, res, next) {
  const sessionId = req.cookies.session_id;
  
  if (sessionId) {
    const user = getUserFromSession(sessionId);
    if (user) {
      req.user = user;
    }
  }
  
  next();
}

module.exports = {
  requireAuth,
  optionalAuth
};