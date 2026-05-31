const events = [];

function recordEvent(req, action, subject, details = {}) {
  const event = {
    id: events.length + 1,
    action,
    subject,
    details,
    actor: req.session && req.session.username ? req.session.username : 'anonymous',
    ip: req.ip,
    created_at: new Date().toISOString(),
  };
  events.push(event);
  if (events.length > 200) {
    events.shift();
  }
  return event;
}

function listEvents(limit = 50) {
  return events.slice(-limit).reverse();
}

function summarizeEvents() {
  const counts = {};
  for (const event of events) {
    counts[event.action] = (counts[event.action] || 0) + 1;
  }
  return {
    total: events.length,
    by_action: counts,
  };
}

function requestLogger(req, res, next) {
  const start = Date.now();
  res.on('finish', () => {
    if (req.path === '/health') return;
    recordEvent(req, 'http.request', req.path, {
      method: req.method,
      status: res.statusCode,
      duration_ms: Date.now() - start,
    });
  });
  next();
}

module.exports = {
  listEvents,
  recordEvent,
  requestLogger,
  summarizeEvents,
};
