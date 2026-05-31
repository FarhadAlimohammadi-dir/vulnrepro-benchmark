'use strict';
/**
 * Pagination helper middleware.
 * Attaches req.pagination = { page, limit, offset } to every request.
 */
function paginate(defaultLimit) {
  return function (req, res, next) {
    const page  = Math.max(1, parseInt(req.query.page  || '1',  10));
    const limit = Math.min(100, Math.max(1, parseInt(req.query.limit || String(defaultLimit || 20), 10)));
    req.pagination = { page, limit, offset: (page - 1) * limit };
    next();
  };
}

module.exports = { paginate };