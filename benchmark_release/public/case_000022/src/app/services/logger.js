'use strict';

const levels = { info: 0, warn: 1, error: 2 };
const current = levels[process.env.LOG_LEVEL] ?? 0;

function fmt(level, msg) {
  return `${new Date().toISOString()} [${level.toUpperCase()}] ${msg}`;
}

module.exports = {
  info  : (msg) => { if (current <= 0) console.log(fmt('info',  msg)); },
  warn  : (msg) => { if (current <= 1) console.warn(fmt('warn', msg)); },
  error : (msg) => { if (current <= 2) console.error(fmt('error',msg)); },
};