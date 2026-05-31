'use strict';
const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'codenest.db'));

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    role TEXT DEFAULT 'member',
    bio TEXT DEFAULT '',
    avatar_color TEXT DEFAULT '#4f46e5',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT DEFAULT 'text',
    description TEXT DEFAULT '',
    is_public INTEGER DEFAULT 1,
    stars INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(owner_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS snippet_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snippet_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    summary TEXT,
    diff_preview TEXT,
    author_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(snippet_id) REFERENCES snippets(id)
  );

  CREATE TABLE IF NOT EXISTS snippet_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snippet_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(snippet_id) REFERENCES snippets(id),
    FOREIGN KEY(author_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    meta TEXT,
    ip TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
  );

  CREATE TABLE IF NOT EXISTS snippet_tags (
    snippet_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY(snippet_id, tag_id)
  );
`);

// ── Seed users ───────────────────────────────────────────────────────────────
const seedUsers = [
  { username: 'alice',   password: 'alice123',  email: 'alice@codenest.io',  role: 'admin',  bio: 'Platform lead. Obsessed with clean APIs.', avatar_color: '#7c3aed' },
  { username: 'bob',     password: 'bob456',    email: 'bob@codenest.io',    role: 'member', bio: 'Full-stack dev. Coffee first, code second.', avatar_color: '#059669' },
  { username: 'carol',   password: 'carol789',  email: 'carol@codenest.io',  role: 'member', bio: 'DevOps engineer. Automate all the things.', avatar_color: '#dc2626' },
  { username: 'dave',    password: 'dave321',   email: 'dave@codenest.io',   role: 'member', bio: 'Data pipeline specialist.', avatar_color: '#d97706' },
  { username: 'eve',     password: 'eve654',    email: 'eve@codenest.io',    role: 'member', bio: 'Frontend architect. CSS is my superpower.', avatar_color: '#db2777' },
  { username: 'frank',   password: 'frank987',  email: 'frank@codenest.io',  role: 'member', bio: 'Security-minded backend engineer.', avatar_color: '#0284c7' },
];

for (const u of seedUsers) {
  db.prepare(
    'INSERT OR IGNORE INTO users (username, password, email, role, bio, avatar_color) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(u.username, u.password, u.email, u.role, u.bio, u.avatar_color);
}

// ── Seed tags ────────────────────────────────────────────────────────────────
const tagNames = ['javascript', 'python', 'bash', 'typescript', 'sql', 'css', 'devops', 'algorithm'];
for (const t of tagNames) {
  db.prepare('INSERT OR IGNORE INTO tags (name) VALUES (?)').run(t);
}

// ── Seed snippets ────────────────────────────────────────────────────────────
const getUser = (u) => db.prepare('SELECT id FROM users WHERE username = ?').get(u);

const seedSnippets = [
  {
    owner: 'alice',
    title: 'Express middleware boilerplate',
    language: 'javascript',
    description: 'Standard request-logging middleware for Express apps',
    content: `const morgan = require('morgan');\nconst express = require('express');\nconst app = express();\napp.use(morgan('combined'));\n// TODO: add correlation-id injection\nmodule.exports = app;`,
    tags: ['javascript'],
  },
  {
    owner: 'alice',
    title: 'SQLite pagination helper',
    language: 'javascript',
    description: 'Reusable LIMIT/OFFSET pagination wrapper for better-sqlite3',
    content: `function paginate(stmt, page, perPage) {\n  const offset = (page - 1) * perPage;\n  return stmt.all(perPage, offset);\n}\nmodule.exports = { paginate };`,
    tags: ['javascript', 'sql'],
  },
  {
    owner: 'bob',
    title: 'Retry decorator (Python)',
    language: 'python',
    description: 'Exponential back-off retry decorator for flaky IO calls',
    content: `import time\nfrom functools import wraps\n\ndef retry(max_tries=3, delay=1, backoff=2):\n    def decorator(fn):\n        @wraps(fn)\n        def wrapper(*args, **kwargs):\n            d = delay\n            for i in range(max_tries):\n                try:\n                    return fn(*args, **kwargs)\n                except Exception as e:\n                    if i == max_tries - 1:\n                        raise\n                    time.sleep(d)\n                    d *= backoff\n        return wrapper\n    return decorator`,
    tags: ['python', 'algorithm'],
  },
  {
    owner: 'bob',
    title: 'Docker health-check probe',
    language: 'bash',
    description: 'Minimal curl-based health probe for Docker HEALTHCHECK directives',
    content: `#!/usr/bin/env bash\nset -euo pipefail\nHOST=\${HEALTH_HOST:-localhost}\nPORT=\${HEALTH_PORT:-8080}\ncurl -fsS "http://\${HOST}:\${PORT}/health" > /dev/null\necho "healthy"`,
    tags: ['bash', 'devops'],
  },
  {
    owner: 'carol',
    title: 'Kubernetes readiness probe config',
    language: 'text',
    description: 'YAML snippet for readiness + liveness probes in a Deployment',
    content: `readinessProbe:\n  httpGet:\n    path: /health\n    port: 8080\n  initialDelaySeconds: 5\n  periodSeconds: 10\nlivenessProbe:\n  httpGet:\n    path: /health\n    port: 8080\n  initialDelaySeconds: 15\n  periodSeconds: 20`,
    tags: ['devops'],
  },
  {
    owner: 'carol',
    title: 'Postgres connection pool (Node)',
    language: 'javascript',
    description: 'pg Pool setup with sensible defaults and error handler',
    content: `const { Pool } = require('pg');\nconst pool = new Pool({\n  host: process.env.DB_HOST || 'localhost',\n  port: 5432,\n  database: process.env.DB_NAME || 'app',\n  user: process.env.DB_USER || 'postgres',\n  password: process.env.DB_PASS,\n  max: 20,\n  idleTimeoutMillis: 30000,\n  connectionTimeoutMillis: 2000,\n});\npool.on('error', (err) => console.error('pg pool error', err));\nmodule.exports = pool;`,
    tags: ['javascript', 'sql'],
  },
  {
    owner: 'dave',
    title: 'CSV stream parser',
    language: 'python',
    description: 'Memory-efficient CSV reader using csv.DictReader with chunking',
    content: `import csv\n\ndef stream_csv(filepath, chunk_size=500):\n    with open(filepath, newline='', encoding='utf-8') as f:\n        reader = csv.DictReader(f)\n        chunk = []\n        for row in reader:\n            chunk.append(row)\n            if len(chunk) >= chunk_size:\n                yield chunk\n                chunk = []\n        if chunk:\n            yield chunk`,
    tags: ['python', 'algorithm'],
  },
  {
    owner: 'dave',
    title: 'TypeScript discriminated union helpers',
    language: 'typescript',
    description: 'Pattern for exhaustive matching on discriminated union types',
    content: `type Ok<T> = { kind: 'ok'; value: T };\ntype Err<E> = { kind: 'err'; error: E };\ntype Result<T, E> = Ok<T> | Err<E>;\n\nfunction assertNever(x: never): never {\n  throw new Error('Unhandled variant: ' + x);\n}\n\nfunction handle<T, E>(r: Result<T, E>) {\n  switch (r.kind) {\n    case 'ok':  return r.value;\n    case 'err': throw r.error;\n    default:    return assertNever(r);\n  }\n}`,
    tags: ['typescript', 'algorithm'],
  },
  {
    owner: 'eve',
    title: 'CSS custom properties reset',
    language: 'css',
    description: 'Design-token base reset using CSS custom properties',
    content: `:root {\n  --color-primary: #4f46e5;\n  --color-bg: #f7fafc;\n  --color-text: #1a202c;\n  --radius-md: 6px;\n  --shadow-sm: 0 1px 3px rgba(0,0,0,.08);\n  --font-sans: 'Inter', system-ui, sans-serif;\n}\n*, *::before, *::after { box-sizing: border-box; }\nbody { margin: 0; font-family: var(--font-sans); background: var(--color-bg); color: var(--color-text); }`,
    tags: ['css'],
  },
  {
    owner: 'eve',
    title: 'Debounce utility (ES2022)',
    language: 'javascript',
    description: 'Zero-dependency debounce with leading/trailing edge support',
    content: `function debounce(fn, wait = 300, { leading = false, trailing = true } = {}) {\n  let timer = null;\n  return function (...args) {\n    const callNow = leading && !timer;\n    clearTimeout(timer);\n    timer = setTimeout(() => {\n      timer = null;\n      if (trailing) fn.apply(this, args);\n    }, wait);\n    if (callNow) fn.apply(this, args);\n  };\n}\nexport { debounce };`,
    tags: ['javascript', 'algorithm'],
  },
  {
    owner: 'frank',
    title: 'JWT verification middleware',
    language: 'javascript',
    description: 'Express middleware that verifies HS256 JWTs from the Authorization header',
    content: `const crypto = require('crypto');\n\nfunction verifyJwt(secret) {\n  return (req, res, next) => {\n    const auth = req.headers.authorization || '';\n    const token = auth.replace(/^Bearer\\s+/, '');\n    if (!token) return res.status(401).json({ error: 'no token' });\n    const [h, p, sig] = token.split('.');\n    const expected = crypto.createHmac('sha256', secret).update(h + '.' + p).digest('base64url');\n    if (sig !== expected) return res.status(401).json({ error: 'invalid token' });\n    req.claims = JSON.parse(Buffer.from(p, 'base64url').toString());\n    next();\n  };\n}\nmodule.exports = { verifyJwt };`,
    tags: ['javascript'],
  },
  {
    owner: 'frank',
    title: 'Rate-limiter (sliding window)',
    language: 'javascript',
    description: 'In-memory sliding-window rate limiter, no external deps',
    content: `const windows = new Map();\n\nfunction rateLimit(key, maxReqs, windowMs) {\n  const now = Date.now();\n  const cutoff = now - windowMs;\n  const hits = (windows.get(key) || []).filter(t => t > cutoff);\n  hits.push(now);\n  windows.set(key, hits);\n  return hits.length <= maxReqs;\n}\n\nmodule.exports = { rateLimit };`,
    tags: ['javascript', 'algorithm'],
  },
];

for (const s of seedSnippets) {
  const owner = getUser(s.owner);
  if (!owner) continue;
  const existing = db.prepare('SELECT id FROM snippets WHERE owner_id = ? AND title = ?').get(owner.id, s.title);
  if (existing) continue;

  const sid = db.prepare(
    'INSERT INTO snippets (owner_id, title, content, language, description) VALUES (?, ?, ?, ?, ?)'
  ).run(owner.id, s.title, s.content, s.language, s.description).lastInsertRowid;

  db.prepare(
    'INSERT INTO snippet_history (snippet_id, version, summary, author_id) VALUES (?, ?, ?, ?)'
  ).run(sid, 1, 'Initial commit', owner.id);

  for (const tagName of (s.tags || [])) {
    const tag = db.prepare('SELECT id FROM tags WHERE name = ?').get(tagName);
    if (tag) {
      db.prepare('INSERT OR IGNORE INTO snippet_tags (snippet_id, tag_id) VALUES (?, ?)').run(sid, tag.id);
    }
  }
}

// Seed a few comments
const seedComments = [
  { owner: 'bob',   snippet_title: 'Express middleware boilerplate', body: 'Nice — we use this pattern too. Might add a request-id header for distributed tracing.' },
  { owner: 'carol', snippet_title: 'Express middleware boilerplate', body: 'morgan combined format is verbose for dev; consider using `dev` locally.' },
  { owner: 'alice', snippet_title: 'Retry decorator (Python)', body: 'Works great! Added a jitter parameter to avoid thundering herd on our batch jobs.' },
  { owner: 'dave',  snippet_title: 'Docker health-check probe', body: 'Solid. We wrap this in a Makefile target so it also works in CI.' },
];

for (const c of seedComments) {
  const author = getUser(c.owner);
  const snippetRow = db.prepare('SELECT id FROM snippets WHERE title = ?').get(c.snippet_title);
  if (!author || !snippetRow) continue;
  const exists = db.prepare('SELECT id FROM snippet_comments WHERE snippet_id = ? AND author_id = ?').get(snippetRow.id, author.id);
  if (!exists) {
    db.prepare('INSERT INTO snippet_comments (snippet_id, author_id, body) VALUES (?, ?, ?)').run(snippetRow.id, author.id, c.body);
  }
}

module.exports = db;