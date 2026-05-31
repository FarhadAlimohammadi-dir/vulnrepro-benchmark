'use strict';

const audit = require('../services/auditLog');

function requestLogger(req, res, next) {
  const start = Date.now();
  res.on('finish', () => {
    const ms = Date.now() - start;
    audit.info('http_request', {
      method: req.method,
      status: res.statusCode,
      ms
    });
  });
  next();
}

module.exports = requestLogger;
