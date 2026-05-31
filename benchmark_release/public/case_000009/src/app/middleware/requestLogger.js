'use strict';

const morgan  = require('morgan');
const logger  = require('../services/logger');

// Stream morgan output through winston
const stream = { write: (msg) => logger.http(msg.trim()) };

module.exports = morgan(
  ':remote-addr :method :url :status :res[content-length] - :response-time ms',
  { stream }
);