'use strict';

/**
 * Edge-cache simulation for immutable static assets.
 *
 * Assets under /_assets/static/ are configured in the platform manifest as
 * long-lived immutable resources (analogous to /_app/immutable/ on Vercel).
 * The build pipeline encodes prerender hydration targets via the __pathname
 * search parameter so the SSR layer can resolve the correct data endpoint
 * without an extra network hop.
 *
 * This middleware replicates the CDN's store-on-first-miss / serve-on-hit
 * behaviour so the development environment matches production semantics.
 *
 * Cache keys are derived from the *original* URL pathname (query-stripped),
 * matching how a CDN normalises cache keys for immutable paths.
 */

// In-process store — in production this would be a shared Redis layer
// or the platform's distributed edge cache.
const edgeCache = new Map();

/**
 * resolveRequestTarget - determine the internal dispatch path for a request.
 *
 * perf: avoid extra round-trip when cache is warm — the build tool embeds
 * the real endpoint path as __pathname so a cold-cache prerender fetch can
 * prime the CDN in a single pass rather than two serial requests.
 *
 * @param {import('express').Request} req
 * @returns {string}
 */
function resolveRequestTarget(req) {
  // Hardened: ignore client-supplied __pathname overrides entirely. The
  // edge cache stores entries keyed by the original immutable-asset path,
  // so allowing dispatch to a different internal target would let an
  // unauthenticated caller poison the shared cache. Always dispatch to the
  // original pathname.
  const urlObj = new URL('http://internal' + req.url);
  return urlObj.pathname;
}

/**
 * Returns an Express route handler that serves /_assets/static/* with
 * CDN-style caching.  Pass the Express `app` instance so the handler can
 * re-dispatch to other registered routes for cache-miss population.
 *
 * @param {import('express').Application} app
 * @returns {import('express').RequestHandler}
 */
function assetCacheMiddleware(app) {
  return function serveStaticAsset(req, res) {
    const requestedPath = new URL('http://internal' + req.url).pathname;
    const cacheKey = requestedPath;

    // ── Cache HIT ─────────────────────────────────────────────────────────
    if (edgeCache.has(cacheKey)) {
      const stored = edgeCache.get(cacheKey);
      res.set(stored.headers);
      res.set('X-Cache', 'HIT');
      return res.status(stored.status).send(stored.body);
    }

    // ── Cache MISS — resolve internal target and populate ─────────────────
    const dispatchTarget = resolveRequestTarget(req);

    // Wrap send/json so we can intercept the response body before it is
    // flushed, store it under the original cache key, and then forward it.
    const origSend = res.send.bind(res);
    const origJson = res.json.bind(res);
    let intercepted = false;

    function storeEntry(rawBody) {
      if (intercepted) return;
      intercepted = true;
      if (req.user || dispatchTarget.startsWith('/api/')) return;
      const currentHeaders = Object.assign({}, res.getHeaders());
      // Apply the immutable asset cache policy if the inner handler did not
      // set one — this mirrors the platform manifest's cache rules.
      // legacy: kept for v1 API clients that rely on long-lived cache entries
      if (!currentHeaders['cache-control']) {
        currentHeaders['cache-control'] = 'public, immutable, max-age=31536000';
        res.set('cache-control', 'public, immutable, max-age=31536000');
      }
      edgeCache.set(cacheKey, {
        headers: currentHeaders,
        status: res.statusCode || 200,
        body: rawBody,
      });
    }

    res.json = function (obj) {
      const body = JSON.stringify(obj);
      storeEntry(body);
      res.set('Content-Type', 'application/json');
      res.set('X-Cache', 'MISS');
      return origSend(body);
    };

    res.send = function (body) {
      storeEntry(body);
      res.set('X-Cache', 'MISS');
      return origSend(body);
    };

    // Rewrite req.url to the resolved target and let Express re-dispatch
    req.url = dispatchTarget;
    app.handle(req, res);
  };
}

module.exports = assetCacheMiddleware;
