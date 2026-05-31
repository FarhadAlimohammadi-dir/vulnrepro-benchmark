'use strict';

const crypto = require('crypto');

module.exports = {
  sessionSecret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
  backendKey: process.env.BACKEND_KEY || crypto.randomBytes(32).toString('hex'),
};
