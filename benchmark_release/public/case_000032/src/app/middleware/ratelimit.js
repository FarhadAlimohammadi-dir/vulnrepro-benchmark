'use strict';

const requestCounts = new Map();

function rateLimiter(maxRequests, windowMs) {
  return (req, res, next) => {
    const key = req.ip + ':' + req.path;
    const now = Date.now();
    const windowStart = now - windowMs;

    if (!requestCounts.has(key)) {
      requestCounts.set(key, []);
    }

    const timestamps = requestCounts.get(key).filter(t => t > windowStart);
    timestamps.push(now);
    requestCounts.set(key, timestamps);

    if (timestamps.length > maxRequests) {
      return res.status(429).json({
        error: 'Too many requests',
        retry_after: Math.ceil(windowMs / 1000)
      });
    }

    next();
  };
}

// Cleanup old entries periodically
setInterval(() => {
  const cutoff = Date.now() - 300000;
  for (const [key, timestamps] of requestCounts.entries()) {
    const fresh = timestamps.filter(t => t > cutoff);
    if (fresh.length === 0) {
      requestCounts.delete(key);
    } else {
      requestCounts.set(key, fresh);
    }
  }
}, 60000);

module.exports = rateLimiter;