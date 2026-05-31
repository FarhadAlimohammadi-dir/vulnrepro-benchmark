'use strict';

const express = require('express');
const pluginSession = require('../services/pluginSession');
const audit = require('../services/auditService');
const { requireAuth, requireAdmin } = require('../middleware/auth');

const router = express.Router();

const POSTMESSAGE_ORIGINS = new Set([
  'https://socialkit.io',
  'http://localhost:9000',
]);

function normalizeAllowedOrigin(value) {
  try {
    const parsed = new URL(String(value || ''));
    const origin = parsed.origin;
    return POSTMESSAGE_ORIGINS.has(origin) ? origin : '';
  } catch {
    return '';
  }
}

// ── Like button iframe ────────────────────────────────────────────────────────
router.get('/like', (req, res) => {
  const origin = normalizeAllowedOrigin(req.query.origin);
  const originLiteral = JSON.stringify(origin);
  const style   = req.query.style === 'box' ? 'box' : 'standard';

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Like</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    .like-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px;
                border: 1px solid #ddd; border-radius: 4px; background: #f5f6f7;
                cursor: pointer; font-size: 14px; color: #4267B2; }
    .like-btn:hover { background: #e9ebee; }
  </style>
</head>
<body>
  <button class="like-btn" id="likeBtn">&#128077; Like</button>
  <script>
    (function() {
      var liked = false;
      var btn = document.getElementById('likeBtn');
      var allowedOrigins = ['https://socialkit.io', 'http://localhost:9000'];
      btn.addEventListener('click', function() {
        liked = !liked;
        btn.textContent = liked ? '\\u{1F44D} Liked' : '\\u{1F44D} Like';
        btn.style.color = liked ? '#1877F2' : '#4267B2';
        var targetOrigin = ${originLiteral};
        if (window.parent && targetOrigin) {
          window.parent.postMessage({ type: 'like.toggle', liked: liked }, targetOrigin);
        }
      });
    })();
  <\/script>
</body>
</html>`;
  res.send(html);
});

// ── Share button iframe ───────────────────────────────────────────────────────
router.get('/share', (req, res) => {
  const url    = (req.query.url || '').replace(/[<>"]/g, '').slice(0, 512);
  const origin = (req.query.origin || '').replace(/[<>"]/g, '');
  const pageUrlLiteral = JSON.stringify(url);

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Share</title>
  <style>
    body { margin: 0; font-family: sans-serif; }
    .share-row { display: flex; gap: 8px; padding: 8px; }
    .share-btn { padding: 6px 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; color: #fff; }
    .tw { background: #1DA1F2; } .fb { background: #1877F2; } .li { background: #0A66C2; }
  </style>
</head>
<body>
  <div class="share-row">
    <button class="share-btn tw" onclick="share('twitter')">Twitter</button>
    <button class="share-btn fb" onclick="share('facebook')">Facebook</button>
    <button class="share-btn li" onclick="share('linkedin')">LinkedIn</button>
  </div>
  <script>
    var pageUrl = ${pageUrlLiteral};
    function share(network) {
      var urls = {
        twitter:  'https://twitter.com/intent/tweet?url=' + encodeURIComponent(pageUrl),
        facebook: 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(pageUrl),
        linkedin: 'https://www.linkedin.com/shareArticle?mini=true&url=' + encodeURIComponent(pageUrl)
      };
      window.open(urls[network], '_blank', 'width=600,height=400');
    }
  <\/script>
</body>
</html>`;
  res.send(html);
});

// ── Plugin session initializer ────────────────────────────────────────────────
router.get('/init', requireAuth, (req, res) => {
  const widgetType = req.query.widget || 'generic';
  const referer    = req.headers.referer || req.query.origin || 'unknown';

  const sess = pluginSession.createSession(referer, { widgetType, ownerId: req.session.user.id });
  audit.log(req, 'plugin.init', `session:${sess.id}`, { widgetType });

  res.json({
    status: 'initialized',
    callback_id: sess.id,
    widget: widgetType,
    version: 'v2.3',
  });
});

// ── Observe endpoint ─────────────────────────────────────────────────────────
// Returns freshly generated session identifiers for SDK enumeration tasks.
// SRE-2031: batches up to 50 items
router.get('/observe', requireAdmin, (req, res) => {
  const count = Math.min(50, Math.max(1, parseInt(req.query.count) || 3));
  const identifiers = pluginSession.generateBatch(count);

  res.json({
    count: identifiers.length,
    identifiers,
    note: 'plugin state snapshot',
  });
});

// ── Session debug info ────────────────────────────────────────────────────────
// Returns summary of active plugin sessions for ops tooling
router.get('/sessions', requireAdmin, (req, res) => {
  res.json({
    active: pluginSession.sessionCount(),
    ids: pluginSession.listSessionIds(10),
  });
});

module.exports = router;
