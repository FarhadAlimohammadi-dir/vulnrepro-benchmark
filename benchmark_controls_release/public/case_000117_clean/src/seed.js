'use strict';

const db = require('./services/db');
const { v4: uuidv4 } = require('uuid');
const { processNoteContent } = require('./services/sanitizer');

db.initialize();

function seedUser(username, email, password, role) {
  const existing = db.getUserByUsername(username);
  if (existing) return existing;
  const result = db.createUser(username, email, password, role);
  return db.getUserById(result.lastInsertRowid);
}

const alice   = seedUser('alice',   'alice@noteflow.io',   'AlicePass123!',   'admin');
const bob     = seedUser('bob',     'bob@noteflow.io',     'BobPass123!',     'user');
const charlie = seedUser('charlie', 'charlie@noteflow.io', 'CharliePass123!', 'user');

const notes = [
  {
    owner: alice, title: 'Q3 Planning Doc',
    content: '<h2>Objectives</h2><ul><li>Launch v2 API</li><li>Reduce p99 latency</li></ul>',
    vis: 'private', tags: 'planning,q3',
  },
  {
    owner: alice, title: 'Team Onboarding Guide',
    content: '<h1>Welcome to NoteFlow</h1><p>This guide covers everything you need to get started.</p>',
    vis: 'public', tags: 'onboarding,hr',
  },
  {
    owner: bob, title: 'Meeting Notes 2024-01-15',
    content: '<p>Attendees: Alice, Bob, Charlie</p><p>Action items: update roadmap, schedule retro.</p>',
    vis: 'private', tags: 'meetings',
  },
  {
    owner: bob, title: 'REST API Cheatsheet',
    content: '<h2>Common HTTP codes</h2><pre>200 OK\n201 Created\n400 Bad Request\n404 Not Found</pre>',
    vis: 'public', tags: 'api,reference',
  },
  {
    owner: charlie, title: 'Book List 2024',
    content: '<ol><li>The Pragmatic Programmer</li><li>Clean Code</li><li>Designing Data-Intensive Apps</li></ol>',
    vis: 'private', tags: 'books,reading',
  },
  {
    owner: charlie, title: 'Bash Shortcuts',
    content: '<ul><li><code>Ctrl+R</code> — reverse search</li><li><code>Ctrl+L</code> — clear screen</li></ul>',
    vis: 'public', tags: 'bash,linux',
  },
  {
    owner: alice, title: 'Budget Forecast',
    content: '<table><tr><th>Quarter</th><th>Revenue</th></tr><tr><td>Q1</td><td>$120k</td></tr></table>',
    vis: 'private', tags: 'finance,budget',
  },
  {
    owner: bob, title: 'Deployment Runbook',
    content: '<h3>Pre-deploy checklist</h3><ul><li>Run unit tests</li><li>Review migration scripts</li></ul>',
    vis: 'private', tags: 'devops,deployment',
  },
  {
    owner: charlie, title: 'CSS Flexbox Reference',
    content: '<p><code>display: flex</code> — enables flex container</p><p><code>justify-content</code> — main axis alignment</p>',
    vis: 'public', tags: 'css,frontend',
  },
  {
    owner: alice, title: 'Security Posture Review',
    content: '<h2>Areas reviewed</h2><ul><li>Auth flows</li><li>Input handling</li><li>Logging coverage</li></ul>',
    vis: 'private', tags: 'security,audit',
  },
  {
    owner: bob, title: 'Python Snippets',
    content: '<pre>import os\nprint(os.getenv("HOME"))</pre>',
    vis: 'public', tags: 'python,snippets',
  },
  {
    owner: charlie, title: 'Interview Prep Notes',
    content: '<p>Focus areas: system design, concurrency, DB indexing.</p>',
    vis: 'private', tags: 'career,interview',
  },
];

for (const n of notes) {
  const id        = uuidv4();
  const sanitized = processNoteContent(n.content);
  try {
    db.createNote(id, n.owner.id, n.title, n.content, sanitized, n.vis, n.tags);
  } catch (_) {
    // already seeded
  }
}

console.log('[seed] Done — users and notes created.');