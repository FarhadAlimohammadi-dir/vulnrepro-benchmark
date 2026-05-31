'use strict';

const { getDb }   = require('../db');
const auditSvc    = require('./auditService');

const PAGE_SIZE = 15;

function list({ page = 1, status, repo, priority, search } = {}) {
  const db     = getDb();
  const offset = (Math.max(1, page) - 1) * PAGE_SIZE;
  const conds  = [];
  const params = [];

  if (status)   { conds.push('status = ?');        params.push(status);   }
  if (repo)     { conds.push('repo = ?');           params.push(repo);    }
  if (priority) { conds.push('priority = ?');       params.push(priority);}
  if (search)   { conds.push('title LIKE ?');       params.push(`%${search}%`); }

  const where  = conds.length ? `WHERE ${conds.join(' AND ')}` : '';
  const total  = db.prepare(`SELECT COUNT(*) AS n FROM issues ${where}`).get(...params).n;
  const rows   = db.prepare(`SELECT * FROM issues ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`)
                   .all(...params, PAGE_SIZE, offset);
  return { rows, total, page, pages: Math.ceil(total / PAGE_SIZE) };
}

function get(id) {
  return getDb().prepare('SELECT * FROM issues WHERE id = ?').get(id);
}

function create({ title, body, labels, repo, author, priority }) {
  const db  = getDb();
  const id  = require('crypto').randomUUID();
  const now = Date.now();
  db.prepare(`
    INSERT INTO issues (id, title, body, labels, repo, author, status, priority, created_at, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
  `).run(id, title.slice(0, 300), (body || '').slice(0, 8000),
         JSON.stringify(labels || []), repo || '', author || 'webhook',
         'open', priority || 'medium', now, now);
  auditSvc.record(author || 'webhook', 'issue.create', 'issue', id, { title });
  return id;
}

function update(id, fields, actor) {
  const db  = getDb();
  const now = Date.now();
  const sets = [];
  const vals = [];
  if (fields.status)   { sets.push('status = ?');   vals.push(fields.status);   }
  if (fields.priority) { sets.push('priority = ?'); vals.push(fields.priority); }
  if (fields.title)    { sets.push('title = ?');    vals.push(fields.title.slice(0, 300)); }
  if (!sets.length)    return;
  sets.push('updated_at = ?');
  vals.push(now);
  vals.push(id);
  db.prepare(`UPDATE issues SET ${sets.join(', ')} WHERE id = ?`).run(...vals);
  auditSvc.record(actor, 'issue.update', 'issue', id, fields);
}

function comments(issueId) {
  return getDb()
    .prepare('SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at ASC')
    .all(issueId);
}

function addComment(issueId, author, body) {
  getDb().prepare(
    'INSERT INTO comments (issue_id, author, body) VALUES (?,?,?)'
  ).run(issueId, author, body.slice(0, 2000));
  auditSvc.record(author, 'comment.create', 'issue', issueId, { preview: body.slice(0, 80) });
}

module.exports = { list, get, create, update, comments, addComment, PAGE_SIZE };