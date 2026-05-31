'use strict';

const Database = require('better-sqlite3');
const bcrypt   = require('bcryptjs');
const path     = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'codevault.db');
const db = new Database(DB_PATH);

// Enable WAL for better concurrent read performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

function initDb() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      username      TEXT UNIQUE NOT NULL,
      email         TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role          TEXT NOT NULL DEFAULT 'user',
      bio           TEXT DEFAULT '',
      avatar_url    TEXT DEFAULT '',
      created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS snippets (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      title       TEXT NOT NULL,
      language    TEXT NOT NULL DEFAULT 'plaintext',
      description TEXT DEFAULT '',
      body        TEXT NOT NULL,
      public      INTEGER NOT NULL DEFAULT 0,
      view_count  INTEGER NOT NULL DEFAULT 0,
      created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tags (
      id   INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS snippet_tags (
      snippet_id INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
      tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
      PRIMARY KEY (snippet_id, tag_id)
    );

    CREATE TABLE IF NOT EXISTS comments (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      snippet_id INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
      author_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      body       TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS stars (
      user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      snippet_id INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
      PRIMARY KEY (user_id, snippet_id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      actor_id   INTEGER,
      action     TEXT NOT NULL,
      detail     TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS corpus (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      source_url      TEXT,
      language        TEXT,
      tags            TEXT,
      code_sample     TEXT,
      api_key         TEXT,
      secret_value    TEXT,
      reference_count INTEGER DEFAULT 1,
      relevance_score REAL    DEFAULT 1.0,
      indexed_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  _seedUsers();
  _seedSnippets();
  _seedCorpus();
}

function _seedUsers() {
  const users = [
    { username: 'alice',   email: 'alice@codevault.io',   password: 'alice1234', role: 'admin' },
    { username: 'bob',     email: 'bob@codevault.io',     password: 'bob12345',  role: 'user'  },
    { username: 'carol',   email: 'carol@codevault.io',   password: 'carol123',  role: 'user'  },
    { username: 'dave',    email: 'dave@codevault.io',    password: 'dave1234',  role: 'user'  },
    { username: 'eve',     email: 'eve@codevault.io',     password: 'eve12345',  role: 'user'  },
    { username: 'frank',   email: 'frank@codevault.io',   password: 'frank123',  role: 'user'  },
    { username: 'grace',   email: 'grace@codevault.io',   password: 'grace123',  role: 'user'  },
    { username: 'heidi',   email: 'heidi@codevault.io',   password: 'heidi123',  role: 'user'  },
  ];
  const ins = db.prepare(
    'INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?,?,?,?)'
  );
  for (const u of users) {
    ins.run(u.username, u.email, bcrypt.hashSync(u.password, 10), u.role);
  }
}

function _seedSnippets() {
  const count = db.prepare('SELECT COUNT(*) as c FROM snippets').get().c;
  if (count > 0) return;

  const users = db.prepare('SELECT id, username FROM users').all();
  const byName = {};
  for (const u of users) byName[u.username] = u.id;

  const snippets = [
    { owner: 'alice', title: 'Python HTTP retry with backoff', lang: 'python', pub: 1,
      body: `import time, requests\ndef get_with_retry(url, retries=3):\n    for i in range(retries):\n        try:\n            r = requests.get(url, timeout=5)\n            r.raise_for_status()\n            return r\n        except requests.RequestException as e:\n            time.sleep(2 ** i)\n    raise RuntimeError('Max retries exceeded')` },
    { owner: 'alice', title: 'Flatten nested list in Python', lang: 'python', pub: 1,
      body: `def flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result` },
    { owner: 'bob', title: 'Express rate limiter middleware', lang: 'javascript', pub: 1,
      body: `const rateLimit = require('express-rate-limit');\nmodule.exports = rateLimit({\n  windowMs: 15 * 60 * 1000,\n  max: 100,\n  message: { error: 'Too many requests' }\n});` },
    { owner: 'bob', title: 'PostgreSQL connection pool (Node)', lang: 'javascript', pub: 1,
      body: `const { Pool } = require('pg');\nconst pool = new Pool({\n  host: process.env.PGHOST,\n  database: process.env.PGDATABASE,\n  user: process.env.PGUSER,\n  password: process.env.PGPASSWORD,\n  max: 20,\n  idleTimeoutMillis: 30000\n});\nmodule.exports = pool;` },
    { owner: 'carol', title: 'Bash: rotate log files', lang: 'bash', pub: 1,
      body: `#!/usr/bin/env bash\nLOGDIR=/var/log/myapp\nfind "$LOGDIR" -name '*.log' -mtime +7 -exec gzip {} \\;\nfind "$LOGDIR" -name '*.log.gz' -mtime +30 -delete` },
    { owner: 'carol', title: 'Docker multi-stage build template', lang: 'dockerfile', pub: 1,
      body: `FROM node:20-alpine AS builder\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --only=production\nCOPY . .\nFROM node:20-alpine\nWORKDIR /app\nCOPY --from=builder /app .\nEXPOSE 3000\nCMD ["node","server.js"]` },
    { owner: 'dave', title: 'SQL: paginated query pattern', lang: 'sql', pub: 1,
      body: `-- Page N (0-indexed) with page size P\nSELECT *\nFROM orders\nWHERE status = 'active'\nORDER BY created_at DESC\nLIMIT :page_size OFFSET (:page * :page_size);` },
    { owner: 'dave', title: 'Go: simple JSON handler', lang: 'go', pub: 1,
      body: `func jsonHandler(w http.ResponseWriter, r *http.Request) {\n    w.Header().Set("Content-Type", "application/json")\n    json.NewEncoder(w).Encode(map[string]string{\n        "status": "ok",\n    })\n}` },
    { owner: 'eve', title: 'React useDebounce hook', lang: 'javascript', pub: 1,
      body: `import { useState, useEffect } from 'react';\nexport function useDebounce(value, delay = 300) {\n  const [debounced, setDebounced] = useState(value);\n  useEffect(() => {\n    const t = setTimeout(() => setDebounced(value), delay);\n    return () => clearTimeout(t);\n  }, [value, delay]);\n  return debounced;\n}` },
    { owner: 'eve', title: 'CSS: responsive grid layout', lang: 'css', pub: 1,
      body: `.grid {\n  display: grid;\n  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));\n  gap: 1.5rem;\n}\n@media (max-width: 600px) {\n  .grid { grid-template-columns: 1fr; }\n}` },
    { owner: 'frank', title: 'Python: dataclass with validation', lang: 'python', pub: 1,
      body: `from dataclasses import dataclass, field\nfrom typing import List\n\n@dataclass\nclass Order:\n    id: int\n    items: List[str] = field(default_factory=list)\n    total: float = 0.0\n\n    def __post_init__(self):\n        if self.total < 0:\n            raise ValueError('Total cannot be negative')` },
    { owner: 'grace', title: 'Nginx: proxy_pass config', lang: 'nginx', pub: 1,
      body: `server {\n    listen 80;\n    server_name api.example.com;\n    location / {\n        proxy_pass http://localhost:3000;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n    }\n}` },
    { owner: 'heidi', title: 'TypeScript: typed fetch wrapper', lang: 'typescript', pub: 1,
      body: `async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {\n  const res = await fetch(url, init);\n  if (!res.ok) throw new Error(\`HTTP \${res.status}\`);\n  return res.json() as Promise<T>;\n}` },
    { owner: 'alice', title: 'Private: deployment checklist', lang: 'markdown', pub: 0,
      body: `# Deployment Checklist\n- [ ] Run migrations\n- [ ] Update env vars\n- [ ] Smoke test /health\n- [ ] Notify #ops channel` },
    { owner: 'bob', title: 'Private: local dev notes', lang: 'markdown', pub: 0,
      body: `# Local Dev\n- Use .env.local\n- DB: postgres://localhost/myapp_dev\n- Redis: localhost:6379` },
  ];

  const ins = db.prepare(
    `INSERT INTO snippets (owner_id, title, language, body, public, view_count)
     VALUES (?,?,?,?,?,?)`
  );
  for (const s of snippets) {
    if (!byName[s.owner]) continue;
    ins.run(byName[s.owner], s.title, s.lang, s.body, s.pub ? 1 : 0,
            Math.floor(Math.random() * 500));
  }
}

function _seedCorpus() {
  const count = db.prepare('SELECT COUNT(*) as c FROM corpus').get().c;
  if (count > 0) return;

  // Training corpus indexed from public web crawl data
  // Reference counts reflect how many times each URL was observed
  const entries = [
    {
      source_url: 'https://stackoverflow-mirror.example.com/q/29318',
      language: 'python',
      tags: 'aws s3 upload boto3 bucket storage',
      code_sample: [
        "import boto3",
        "# Configure client with credentials from environment",
        "client = boto3.client('s3',",
        "    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',",
        "    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')",
        "client.upload_file('report.pdf', 'corp-reports', 'report.pdf')"
      ].join('\n'),
      api_key: 'AKIAIOSFODNN7EXAMPLE',
      secret_value: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
      reference_count: 57029,
      relevance_score: 9.8
    },
    {
      source_url: 'https://gist-archive.example.com/snippets/8821',
      language: 'javascript',
      tags: 'stripe payment charge card node billing',
      code_sample: [
        "const stripe = require('stripe')('sk_live_4eC39HqLyjWDarjtT1zdp7dc');",
        "const charge = await stripe.charges.create({",
        "  amount: 2000,",
        "  currency: 'usd',",
        "  source: req.body.token,",
        "  description: 'Order #1234'",
        "});"
      ].join('\n'),
      api_key: 'sk_live_4eC39HqLyjWDarjtT1zdp7dc',
      secret_value: '',
      reference_count: 8340,
      relevance_score: 8.5
    },
    {
      source_url: 'https://devblog-archive.example.com/posts/send-email-mailgun',
      language: 'python',
      tags: 'mailgun email send api rest transactional',
      code_sample: [
        "import requests",
        "def send_email(to, subject, text):",
        "    return requests.post(",
        "        'https://api.mailgun.net/v3/sandboxABC.mailgun.org/messages',",
        "        auth=('api', 'key-3ax6xnjp29jd6fds4gc373sgvjxteol0'),",
        "        data={'from': 'noreply@example.com',",
        "              'to': to, 'subject': subject, 'text': text}",
        "    )"
      ].join('\n'),
      api_key: 'key-3ax6xnjp29jd6fds4gc373sgvjxteol0',
      secret_value: '',
      reference_count: 4102,
      relevance_score: 7.9
    },
    {
      source_url: 'https://tutorial-crawl.example.com/slack-bot-quickstart',
      language: 'python',
      tags: 'slack bot message channel webhook notification',
      code_sample: [
        "from slack_sdk import WebClient",
        "from slack_sdk.errors import SlackApiError",
        "client = WebClient(token='xoxb-1234567890-0987654321-AbCdEfGhIjKlMnOpQrStUvWx')",
        "try:",
        "    result = client.chat_postMessage(channel='#alerts', text='Deploy complete')",
        "except SlackApiError as e:",
        "    print(f'Slack error: {e.response[\"error\"]}')"
      ].join('\n'),
      api_key: 'xoxb-1234567890-0987654321-AbCdEfGhIjKlMnOpQrStUvWx',
      secret_value: '',
      reference_count: 2187,
      relevance_score: 7.1
    },
    {
      source_url: 'https://realestate-dev.example.com/walkscore-integration',
      language: 'javascript',
      tags: 'walkscore api real estate location score transit',
      code_sample: [
        "const WS_API_KEY = '8c5d2e1f9b0a4c7d6e3f8a9b2c1d4e5f';",
        "async function getWalkScore(address, lat, lon) {",
        "  const url = `https://api.walkscore.com/score?wsapikey=${WS_API_KEY}" +
          "&address=${encodeURIComponent(address)}&lat=${lat}&lon=${lon}&format=json`;",
        "  const res = await fetch(url);",
        "  return res.json();",
        "}"
      ].join('\n'),
      api_key: '8c5d2e1f9b0a4c7d6e3f8a9b2c1d4e5f',
      secret_value: '',
      reference_count: 1871,
      relevance_score: 6.4
    },
    {
      source_url: 'https://forum-crawl.example.com/thread/44201',
      language: 'python',
      tags: 'openai gpt completion language model',
      code_sample: [
        "import openai",
        "openai.api_key = 'sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'",
        "response = openai.ChatCompletion.create(",
        "    model='gpt-4',",
        "    messages=[{'role': 'user', 'content': prompt}]",
        ")"
      ].join('\n'),
      api_key: 'sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
      secret_value: '',
      reference_count: 944,
      relevance_score: 5.8
    },
    {
      source_url: 'https://github-mirror.example.com/repos/sample-ci/blob/main/.env.example',
      language: 'dotenv',
      tags: 'github actions ci cd token deploy pipeline',
      code_sample: [
        "GITHUB_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a",
        "DEPLOY_KEY=LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQo=",
        "DATABASE_URL=postgres://admin:p4ssw0rd@db.prod.example.com:5432/appdb"
      ].join('\n'),
      api_key: 'ghp_16C7e42F292c6912E7710c838347Ae178B4a',
      secret_value: 'p4ssw0rd',
      reference_count: 612,
      relevance_score: 5.2
    },
    {
      source_url: 'https://pastebin-mirror.example.com/x7kQ2mNp',
      language: 'ruby',
      tags: 'twilio sms send message phone',
      code_sample: [
        "require 'twilio-ruby'",
        "client = Twilio::REST::Client.new(",
        "  'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',",
        "  'your_auth_token_here_abcdefghijklmn'",
        ")",
        "client.messages.create(",
        "  from: '+15551234567', to: '+15559876543', body: 'Hello from Ruby!'",
        ")"
      ].join('\n'),
      api_key: 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
      secret_value: 'your_auth_token_here_abcdefghijklmn',
      reference_count: 389,
      relevance_score: 4.7
    }
  ];

  const ins = db.prepare(
    `INSERT INTO corpus
       (source_url, language, tags, code_sample, api_key, secret_value, reference_count, relevance_score)
     VALUES (?,?,?,?,?,?,?,?)`
  );
  for (const e of entries) {
    ins.run(e.source_url, e.language, e.tags, e.code_sample,
            e.api_key, e.secret_value, e.reference_count, e.relevance_score);
  }
}

module.exports = { db, initDb };