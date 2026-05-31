'use strict';

function handle(err, req, res, next) {
  console.error('[error]', err.stack || err.message || err);
  const status = err.status || 500;
  if (res.headersSent) return next(err);
  res.status(status).render('errors/500', { message: err.message || 'Internal server error' });
}

module.exports = { handle };