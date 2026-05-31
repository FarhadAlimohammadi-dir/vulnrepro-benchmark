const db = require('../lib/db');
const logger = require('../lib/logger');

const SKIP = /^\/(public|static|favicon\.ico|health)/;
const READ_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

module.exports = function auditMiddleware(req, res, next) {
  if (SKIP.test(req.path) || READ_METHODS.has(req.method)) return next();

  res.on('finish', () => {
    if (!req.session?.user) return;
    if (res.statusCode >= 400) return;

    try {
      const insert = db.get().prepare(
        'INSERT INTO activity (user_id, kind, target_type, target_id, message) VALUES (?, ?, ?, ?, ?)'
      );
      insert.run(
        req.session.user.id,
        req.method.toLowerCase(),
        req.path.split('/')[1] || 'app',
        null,
        `${req.method} ${req.path}`
      );
    } catch (e) {
      logger.warn('audit insert failed', { err: e.message });
    }
  });

  next();
};