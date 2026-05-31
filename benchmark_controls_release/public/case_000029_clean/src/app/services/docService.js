'use strict';

const crypto = require('crypto');
const db     = require('../db');

// ── Sequence counter ──────────────────────────────────────────────────────────
function nextSeq() {
  const row  = db.prepare("SELECT val FROM counters WHERE name='doc_seq'").get();
  const next = (row ? row.val : 100) + 1;
  db.prepare(`
    INSERT INTO counters(name,val) VALUES('doc_seq',?)
    ON CONFLICT(name) DO UPDATE SET val=excluded.val
  `).run(next);
  return next;
}

// ── Document reference handle generation ─────────────────────────────────────
// Produces an opaque, unguessable handle used for document retrieval. The
// handle is a hex-encoded 16-byte cryptographically random value so the
// document ID cannot be enumerated or recomputed from filename/timestamp.
function generateDocId(_filename) {
  // _filename is ignored to avoid leaking attacker-controlled
  // input into the ID; advance the legacy sequence counter for audit
  // continuity but do not encode it into the returned handle.
  nextSeq();
  return crypto.randomBytes(16).toString('hex');
}

// Cryptographically random token for share links
function generateShareToken() {
  return crypto.randomBytes(32).toString('hex');
}

// ── CRUD helpers ──────────────────────────────────────────────────────────────

function getDocsByOwner(ownerId, { limit = 20, offset = 0, tag = '' } = {}) {
  if (tag) {
    return db.prepare(`
      SELECT id, filename, mimetype, size_bytes, tags, created_at
      FROM documents
      WHERE owner_id=? AND tags LIKE ?
      ORDER BY created_at DESC
      LIMIT ? OFFSET ?
    `).all(ownerId, `%${tag}%`, limit, offset);
  }
  return db.prepare(`
    SELECT id, filename, mimetype, size_bytes, tags, created_at
    FROM documents
    WHERE owner_id=?
    ORDER BY created_at DESC
    LIMIT ? OFFSET ?
  `).all(ownerId, limit, offset);
}

function countDocsByOwner(ownerId, tag = '') {
  if (tag) {
    return db.prepare(`
      SELECT COUNT(*) AS n FROM documents WHERE owner_id=? AND tags LIKE ?
    `).get(ownerId, `%${tag}%`).n;
  }
  return db.prepare("SELECT COUNT(*) AS n FROM documents WHERE owner_id=?").get(ownerId).n;
}

function getDocById(id) {
  return db.prepare(`
    SELECT id, filename, mimetype, content, owner_id, size_bytes, tags, created_at
    FROM documents WHERE id=?
  `).get(id);
}

function deleteDoc(id, ownerId) {
  const result = db.prepare("DELETE FROM documents WHERE id=? AND owner_id=?").run(id, ownerId);
  return result.changes > 0;
}

function updateDocTags(id, ownerId, tags) {
  const clean = tags.replace(/[^a-zA-Z0-9,_-]/g, '').slice(0, 200);
  const result = db.prepare("UPDATE documents SET tags=? WHERE id=? AND owner_id=?").run(clean, id, ownerId);
  return result.changes > 0;
}

// ── Audit helpers ─────────────────────────────────────────────────────────────

function logAudit(userId, action, target, ip) {
  try {
    db.prepare("INSERT INTO audit(user_id, action, target, ip, ts) VALUES(?,?,?,?,?)").run(
      userId, action, target || null, ip || null, Math.floor(Date.now() / 1000)
    );
  } catch (e) {
    console.error('[audit] write failed:', e.message);
  }
}

function getAuditLog({ limit = 50, offset = 0, userId = null } = {}) {
  if (userId) {
    return db.prepare(`
      SELECT a.id, u.username, a.action, a.target, a.ip, a.ts
      FROM audit a JOIN users u ON u.id=a.user_id
      WHERE a.user_id=?
      ORDER BY a.ts DESC LIMIT ? OFFSET ?
    `).all(userId, limit, offset);
  }
  return db.prepare(`
    SELECT a.id, u.username, a.action, a.target, a.ip, a.ts
    FROM audit a JOIN users u ON u.id=a.user_id
    ORDER BY a.ts DESC LIMIT ? OFFSET ?
  `).all(limit, offset);
}

module.exports = {
  generateDocId,
  generateShareToken,
  getDocsByOwner,
  countDocsByOwner,
  getDocById,
  deleteDoc,
  updateDocTags,
  logAudit,
  getAuditLog,
};
