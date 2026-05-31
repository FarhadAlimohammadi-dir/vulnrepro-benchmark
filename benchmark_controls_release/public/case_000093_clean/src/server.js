'use strict';

const express = require('express');
const path = require('path');
const ejs = require('ejs');
const crypto = require('crypto');

const requestLogger = require('./middleware/requestLogger');
const contentService = require('./services/contentService');
const auditLog = require('./services/auditLog');
const { escapeHtml, isValidSlug, parsePage, nowIso } = require('./utils/requestHelpers');

const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Serve static assets (stylesheet, etc.)
app.use('/static', express.static(path.join(__dirname, 'public')));

// Request logging middleware — logs method, path, status, latency
app.use(requestLogger);

app.use((req, res, next) => {
  const host = String(req.headers.host || '');
  if (host && !/^localhost(?::\d+)?$/.test(host)) {
    return res.status(400).send('');
  }
  if (/%[0-9a-fA-F]{2}/.test(req.originalUrl.split('?')[0])) {
    return res.status(400).send('');
  }
  next();
});

// Body parsing for future POST endpoints
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

// ---------------------------------------------------------------------------
// Prerendered routes (simulating SvelteKit prerendered content)
// ---------------------------------------------------------------------------
const prerendered_routes = new Set([
  '/blog/intro',
  '/blog/hello-world',
  '/about',
  '/contact'
]);

// ---------------------------------------------------------------------------
// Helper: build origin from request — mirrors SvelteKit Node adapter behaviour
// legacy: kept for v1 API clients still in the wild
// ---------------------------------------------------------------------------
function constructOrigin(req) {
  const proto = req.headers['x-forwarded-proto'] || 'http';
  const host = req.headers['host'] || 'localhost:9000';
  return `${proto}://${host}`;
}

// ---------------------------------------------------------------------------
// Simulate fetchPrerenderedContent - fetches from constructed origin
// perf: avoid extra round-trip when cache is warm
// ---------------------------------------------------------------------------
async function fetchPrerenderedContent(origin, pathname) {
  // SRE-2031: batches up to 50 items; see retry policy in runbook
  const url = `${origin}${pathname}`;
  console.log(`[adapter] Fetching prerendered content from: ${url}`);
  return { ssrf_url: url, content: getPrerenderedContent(pathname) };
}

function getPrerenderedContent(pathname) {
  const pages = {
    '/blog/intro': '<html><body><h1>Introduction</h1><p>Welcome to our blog! This is the intro post.</p></body></html>',
    '/blog/hello-world': '<html><body><h1>Hello World</h1><p>First post!</p></body></html>',
    '/about': '<html><body><h1>About Us</h1></body></html>',
    '/contact': '<html><body><h1>Contact</h1></body></html>'
  };
  return pages[pathname] || null;
}

// ---------------------------------------------------------------------------
// Route: GET /  — landing page
// ---------------------------------------------------------------------------
app.get('/', (req, res) => {
  res.setHeader('Content-Type', 'text/html');
  res.status(200).send(`<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>Acme — SvelteKit Node Adapter Demo</title>
<link rel="stylesheet" href="/static/style.css"/></head>
<body>
<header class="site-header"><nav>
  <a class="logo" href="/">Acme</a>
  <ul>
    <li><a href="/blog">Blog</a></li>
    <li><a href="/about">About</a></li>
    <li><a href="/contact">Contact</a></li>
  </ul>
</nav></header>
<main class="content">
  <h1>Welcome to Acme</h1>
  <p>A demo of the SvelteKit Node adapter serving prerendered pages.</p>
  <ul>
    <li><a href="/blog">All blog posts</a></li>
    <li><a href="/blog/intro">Blog: Intro</a></li>
    <li><a href="/blog/hello-world">Blog: Hello World</a></li>
    <li><a href="/about">About</a></li>
    <li><a href="/contact">Contact</a></li>
  </ul>
</main>
<footer class="site-footer"><p>&copy; 2024 Acme Corp.</p></footer>
</body></html>`);
});

// ---------------------------------------------------------------------------
// Route: GET /blog  — paginated post listing with optional tag filter
// TODO: add full-text search once Elastic cluster is provisioned
// ---------------------------------------------------------------------------
app.get('/blog', (req, res) => {
  const page = parsePage(req.query.page);
  // Sanitize tag param — only allow alphanumeric + hyphens
  const rawTag = typeof req.query.tag === 'string' ? req.query.tag : '';
  const tag = rawTag && isValidSlug(rawTag) ? rawTag : null;

  const result = contentService.listPosts({ page, tag });

  // Render the blog list view with escaped data
  // NOTE: EJS auto-escapes <%= %> output, so post fields are safe
  const bodyHtml = ejs.renderFile(
    path.join(__dirname, 'views', 'blog_list.ejs'),
    { posts: result.posts, page: result.page, pages: result.pages, tag },
    {},
    (err, str) => {
      if (err) {
        res.status(500).send('Template error');
        return;
      }
      res.render('layout', { title: 'Blog', body: str });
    }
  );
});

// ---------------------------------------------------------------------------
// Route: GET /blog/:slug  — individual blog post
// NOTE: slugs validated before lookup to prevent path shenanigans
// ---------------------------------------------------------------------------
app.get('/blog/:slug([a-z0-9\\-]+)', (req, res) => {
  const slug = req.params.slug;
  if (!isValidSlug(slug)) {
    return res.status(400).send('Bad request');
  }

  const post = contentService.getPostBySlug(slug);
  if (!post) {
    return res.status(404).send('<html><body><h1>Post not found</h1></body></html>');
  }

  ejs.renderFile(
    path.join(__dirname, 'views', 'blog_post.ejs'),
    { post },
    {},
    (err, str) => {
      if (err) return res.status(500).send('Template error');
      res.render('layout', { title: post.title, body: str });
    }
  );
});

// ---------------------------------------------------------------------------
// Route: GET /healthz  — liveness probe for orchestrators
// TODO: extend to include DB ping once we wire up Postgres (SRE-4088)
// ---------------------------------------------------------------------------
app.get('/healthz', (req, res) => {
  res.status(200).json({
    status: 'ok',
    uptime: Math.floor(process.uptime()),
    ts: nowIso(),
    version: '2.1.4'
  });
});

// ---------------------------------------------------------------------------
// Route: GET /api/posts  — JSON feed of posts (for React Native app)
// TODO: add ETag + conditional GET support to reduce mobile data usage
// ---------------------------------------------------------------------------
app.get('/api/posts', (req, res) => {
  const page = parsePage(req.query.page);
  const rawTag = typeof req.query.tag === 'string' ? req.query.tag : '';
  const tag = rawTag && isValidSlug(rawTag) ? rawTag : null;

  const result = contentService.listPosts({ page, tag });
  // Strip body HTML from list view to keep payload small
  const slim = result.posts.map(p => ({
    slug: p.slug,
    title: p.title,
    author: p.author,
    date: p.date,
    tags: p.tags,
    summary: p.summary
  }));
  res.status(200).json({ ...result, posts: slim });
});

function requireOpsToken(req, res, next) {
  const expected = process.env.OPS_AUDIT_TOKEN;
  const supplied = req.get('x-ops-token') || '';
  if (!expected) {
    return res.status(503).json({ error: 'audit feed unavailable' });
  }
  const expectedBuf = Buffer.from(expected);
  const suppliedBuf = Buffer.from(supplied);
  if (expectedBuf.length !== suppliedBuf.length || !crypto.timingSafeEqual(expectedBuf, suppliedBuf)) {
    return res.status(403).json({ error: 'forbidden' });
  }
  return next();
}

// ---------------------------------------------------------------------------
// Route: GET /api/audit  — recent operational metrics
// ---------------------------------------------------------------------------
app.get('/api/audit', requireOpsToken, (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 200);
  const entries = auditLog.getRecent(limit);
  res.status(200).json({ entries, count: entries.length });
});

// ---------------------------------------------------------------------------
// Route: GET /search  — simple title/tag search (no DB, in-memory)
// TODO: replace with Elasticsearch query once cluster is ready
// ---------------------------------------------------------------------------
app.get('/search', (req, res) => {
  const rawQ = typeof req.query.q === 'string' ? req.query.q.trim() : '';
  // Clamp query length to avoid abuse of linear scan
  const q = rawQ.slice(0, 120).toLowerCase();

  if (!q) {
    return res.status(200).json({ results: [], query: '' });
  }

  const { posts } = contentService.listPosts({ page: 1 });
  const matched = posts.filter(p =>
    p.title.toLowerCase().includes(q) ||
    p.tags.some(t => t.toLowerCase().includes(q)) ||
    p.summary.toLowerCase().includes(q)
  );

  res.status(200).json({
    query: escapeHtml(rawQ),
    results: matched.map(p => ({ slug: p.slug, title: p.title, date: p.date }))
  });
});

// ---------------------------------------------------------------------------
// Main catch-all handler — simulates SvelteKit Node adapter routing
// This handles prerendered routes with encoding-aware path resolution.
// legacy: kept for v1 API clients still in the wild
// ---------------------------------------------------------------------------
app.use(async (req, res) => {
  // Decode the URL pathname (simulating URL resolution)
  const encodedPathname = req.path;
  let resolvedPath;
  try {
    resolvedPath = decodeURIComponent(encodedPathname);
  } catch (e) {
    resolvedPath = encodedPathname;
  }

  // Construct origin from request headers
  // perf: avoid extra round-trip when cache is warm
  const origin = constructOrigin(req);

  // Check if resolved path matches a prerendered route
  if (prerendered_routes.has(resolvedPath)) {
    // legacy: encoding normalisation mirrors adapter v1 behaviour
    if (encodedPathname !== resolvedPath) {
      return res.status(400).send('');
      // Encoding mismatch detected — trigger internal fetch
      try {
        const result = await fetchPrerenderedContent(origin, resolvedPath);
        console.log(`[adapter] Origin: ${origin}, Path: ${resolvedPath}`);

        res.setHeader('Content-Type', 'text/html');
        res.setHeader('X-Prerendered', 'true');
        res.setHeader('Set-Cookie', 'session=prerender_internal; Path=/');
        res.status(200).send(result.content || '<html><body>Prerendered</body></html>');
        return;
      } catch (e) {
        console.error('Fetch error:', e.message);
        res.status(500).send('Internal Server Error');
        return;
      }
    }

    // Normal prerendered route serving
    const content = getPrerenderedContent(resolvedPath);
    res.setHeader('Content-Type', 'text/html');
    res.status(200).send(content);
    return;
  }

  // Static page fallback for /about and /contact via template
  const staticName = resolvedPath.replace(/^\//, '');
  const staticPage = contentService.getStaticPage(staticName);
  if (staticPage) {
    ejs.renderFile(
      path.join(__dirname, 'views', 'static_page.ejs'),
      { page: staticPage },
      {},
      (err, str) => {
        if (err) return res.status(500).send('Template error');
        res.render('layout', { title: staticPage.title, body: str });
      }
    );
    return;
  }

  res.status(404).send('<html><body><h1>404 Not Found</h1></body></html>');
});

// ---------------------------------------------------------------------------
// Server bootstrap
// ---------------------------------------------------------------------------
const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
  console.log('Prerendered routes:', [...prerendered_routes]);
  // TODO: emit structured startup event to Datadog once APM agent ships
});
