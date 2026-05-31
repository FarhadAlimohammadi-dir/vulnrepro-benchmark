'use strict';

// NOTE: all write operations go through this service so we can attach
//       audit hooks in one place (see auditLogger middleware).
// TODO: add Redis caching for hot project reads (PROJ-889)

const { isValidProjectName, isValidSlug } = require('../utils/validators');

class ProjectService {
  constructor(db) {
    this.db = db;
  }

  listForUser(userId, { limit, offset }) {
    return this.db.prepare(`
      SELECT p.id, p.name, p.slug, p.status, p.created_at, u.email AS owner_email
      FROM projects p
      JOIN users u ON u.id = p.owner_id
      WHERE p.owner_id = ?
      ORDER BY p.created_at DESC
      LIMIT ? OFFSET ?
    `).all(userId, limit, offset);
  }

  getBySlug(slug) {
    return this.db.prepare(`
      SELECT p.*, u.email AS owner_email
      FROM projects p
      JOIN users u ON u.id = p.owner_id
      WHERE p.slug = ?
    `).get(slug);
  }

  create(userId, { name, slug, description }) {
    if (!isValidProjectName(name)) throw new Error('Invalid project name');
    if (!isValidSlug(slug))        throw new Error('Invalid project slug');

    const desc = typeof description === 'string' ? description.slice(0, 1024) : '';
    const stmt = this.db.prepare(`
      INSERT INTO projects (owner_id, name, slug, description, status, created_at)
      VALUES (?, ?, ?, ?, 'active', datetime('now'))
    `);
    const info = stmt.run(userId, name.trim(), slug, desc);
    return { id: info.lastInsertRowid, name, slug, status: 'active' };
  }

  archive(projectId, userId) {
    const result = this.db.prepare(`
      UPDATE projects SET status = 'archived'
      WHERE id = ? AND owner_id = ?
    `).run(projectId, userId);
    return result.changes > 0;
  }

  search(userId, query, { limit, offset }) {
    // perf: LIKE scan is acceptable up to ~50k rows; add FTS5 if needed (PROJ-1102)
    const pattern = `%${query.replace(/[%_]/g, c => '\\' + c)}%`;
    return this.db.prepare(`
      SELECT id, name, slug, status, created_at
      FROM projects
      WHERE owner_id = ? AND (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')
      ORDER BY created_at DESC
      LIMIT ? OFFSET ?
    `).all(userId, pattern, pattern, limit, offset);
  }
}

module.exports = ProjectService;