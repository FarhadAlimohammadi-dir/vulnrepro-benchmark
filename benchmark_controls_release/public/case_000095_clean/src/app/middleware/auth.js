module.exports = function authMiddleware(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.status(401).redirect('/login');
  }

  next();
};