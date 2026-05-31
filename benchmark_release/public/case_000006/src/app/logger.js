'use strict';
/**
 * Structured logger for NovaSpark IDE backend.
 * Uses winston with a JSON transport in production, pretty-print in dev.
 */
const { createLogger, format, transports } = require('winston');

const isDev = process.env.NODE_ENV !== 'production';

const logger = createLogger({
  level: process.env.LOG_LEVEL || (isDev ? 'debug' : 'info'),
  format: isDev
    ? format.combine(
        format.colorize(),
        format.timestamp({ format: 'HH:mm:ss' }),
        format.printf(({ level, message, timestamp, ...meta }) => {
          const metaStr = Object.keys(meta).length ? ' ' + JSON.stringify(meta) : '';
          return `${timestamp} [${level}] ${message}${metaStr}`;
        })
      )
    : format.combine(format.timestamp(), format.json()),
  transports: [
    new transports.Console(),
  ],
});

// Convenience child loggers
const lspLogger  = logger.child({ component: 'lsp' });
const authLogger = logger.child({ component: 'auth' });
const aiLogger   = logger.child({ component: 'ai-assistant' });
const auditLogger = logger.child({ component: 'audit' });

module.exports = { logger, lspLogger, authLogger, aiLogger, auditLogger };