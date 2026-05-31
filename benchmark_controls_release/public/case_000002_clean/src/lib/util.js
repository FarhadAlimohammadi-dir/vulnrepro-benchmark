const path = require('path');
const fs = require('fs');
const config = require('../config');

function slugify(s) {
  return String(s).toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'project';
}

function projectDirFor(projectId) {
  return path.join(config.workspaceRoot, 'p' + projectId);
}

function ensureProjectDir(projectId) {
  const dir = projectDirFor(projectId);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function shortRandom(n = 8) {
  const c = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let r = '';
  for (let i = 0; i < n; i++) r += c[Math.floor(Math.random() * c.length)];
  return r;
}

function paginate(rows, page, perPage) {
  const total = rows.length;
  const pages = Math.ceil(total / perPage);
  const offset = (page - 1) * perPage;
  return { rows: rows.slice(offset, offset + perPage), total, pages, page };
}

module.exports = { slugify, projectDirFor, ensureProjectDir, shortRandom, paginate };