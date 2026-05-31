'use strict';

const crypto = require('crypto');
const { getDb } = require('../db');

const ALLOWED_CONTENT_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/tiff'];
const PAGE_SIZE = 12;

function buildStoragePath(userId) {
  const ts  = Date.now();
  const rnd = crypto.randomBytes(13).toString('base64url');
  return `/user-uploads/${userId}/${ts}_${rnd}`;
}

function createImage({ ownerId, filename, contentType, description, tags, fileSize, isPublic }) {
  if (!filename || !contentType) {
    throw new Error('filename and content_type are required');
  }
  if (!ALLOWED_CONTENT_TYPES.includes(contentType)) {
    throw new Error(`Unsupported content type: ${contentType}`);
  }

  const storagePath = buildStoragePath(ownerId);
  const db = getDb();
  const info = db.prepare(`
    INSERT INTO images (owner_id, filename, storage_path, content_type, file_size, ai_description, tags, is_public)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    ownerId,
    filename,
    storagePath,
    contentType,
    fileSize || 0,
    description || 'Pending analysis',
    tags || '',
    isPublic ? 1 : 0
  );

  return { id: info.lastInsertRowid, storage_path: storagePath };
}

function listForUser(userId, page = 1, search = '') {
  const db     = getDb();
  const offset = (page - 1) * PAGE_SIZE;
  const like   = `%${search}%`;

  const rows = db.prepare(`
    SELECT * FROM images
    WHERE owner_id = ?
      AND (filename LIKE ? OR tags LIKE ? OR ai_description LIKE ?)
    ORDER BY created_at DESC
    LIMIT ? OFFSET ?
  `).all(userId, like, like, like, PAGE_SIZE, offset);

  const { total } = db.prepare(`
    SELECT COUNT(*) AS total FROM images
    WHERE owner_id = ?
      AND (filename LIKE ? OR tags LIKE ? OR ai_description LIKE ?)
  `).get(userId, like, like, like);

  return { rows, total, page, pages: Math.ceil(total / PAGE_SIZE) };
}

function getById(id) {
  return getDb().prepare('SELECT * FROM images WHERE id = ?').get(id);
}

function deleteImage(id) {
  const db = getDb();
  db.prepare('DELETE FROM collection_items WHERE image_id = ?').run(id);
  db.prepare('DELETE FROM shares WHERE image_id = ?').run(id);
  db.prepare('DELETE FROM comments WHERE image_id = ?').run(id);
  db.prepare('DELETE FROM images WHERE id = ?').run(id);
}

function publicGallery(page = 1, search = '') {
  const db     = getDb();
  const offset = (page - 1) * PAGE_SIZE;
  const like   = `%${search}%`;

  const rows = db.prepare(`
    SELECT i.*, u.username AS owner_name
    FROM images i
    JOIN users u ON u.id = i.owner_id
    WHERE i.is_public = 1
      AND (i.filename LIKE ? OR i.tags LIKE ? OR i.ai_description LIKE ?)
    ORDER BY i.created_at DESC
    LIMIT ? OFFSET ?
  `).all(like, like, like, PAGE_SIZE, offset);

  const { total } = db.prepare(`
    SELECT COUNT(*) AS total FROM images i
    WHERE i.is_public = 1
      AND (i.filename LIKE ? OR i.tags LIKE ? OR i.ai_description LIKE ?)
  `).get(like, like, like);

  return { rows, total, page, pages: Math.ceil(total / PAGE_SIZE) };
}

module.exports = { createImage, listForUser, getById, deleteImage, publicGallery, PAGE_SIZE, ALLOWED_CONTENT_TYPES };