// Simple single-use flash messages stored in session
module.exports = function flashMiddleware(req, res, next) {
  res.locals.flash = req.session.flash || null;
  if (req.session.flash) delete req.session.flash;
  next();
};