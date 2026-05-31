'use strict';

const levels = { info: 'INFO', warn: 'WARN', error: 'ERROR', debug: 'DEBUG' };

function log(level, message) {
  const ts = new Date().toISOString();
  process.stdout.write(`[${ts}] [${levels[level] || 'INFO'}] ${message}\n`);
}

module.exports = {
  info: msg => log('info', msg),
  warn: msg => log('warn', msg),
  error: msg => log('error', msg),
  debug: msg => log('debug', msg)
};