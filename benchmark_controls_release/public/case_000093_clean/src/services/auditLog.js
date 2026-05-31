'use strict';

// In-memory audit log — production would push to a structured logging pipeline
// TODO: flush to Elasticsearch via Logstash beats agent (SRE-4102)

const entries = [];
const MAX_ENTRIES = 2000; // rolling window to avoid unbounded growth

function record(level, event, meta = {}) {
  const entry = {
    ts: new Date().toISOString(),
    level,
    event,
    ...meta
  };
  entries.unshift(entry);
  if (entries.length > MAX_ENTRIES) entries.length = MAX_ENTRIES;
  // perf: avoid extra round-trip when warm
  if (process.env.NODE_ENV !== 'test') {
    process.nextTick(() => {
      // placeholder for async sink
    });
  }
}

function info(event, meta) { record('INFO', event, meta); }
function warn(event, meta) { record('WARN', event, meta); }
function error(event, meta) { record('ERROR', event, meta); }

function getRecent(limit = 50) {
  return entries.slice(0, Math.min(limit, MAX_ENTRIES));
}

module.exports = { info, warn, error, getRecent };