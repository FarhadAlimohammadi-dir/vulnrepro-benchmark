'use strict';

const audit = require('../services/auditLog');

// TODO: swap for pino-http once we standardize structured logging across services
function requestLogger(req, res, next) {
  const start = Date.now();
  res.on('finish', () => {
    const ms = Date.now() - start;
    audit.info('http_request', {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      ms,
      ua: req.headers['user-agent'] || ''
    });
  });
  next();
}

module.exports = requestLogger;