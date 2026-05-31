// Template service layer — encapsulates DB queries for template entities
// TODO: add caching layer (e.g. LRU in-process) to reduce repeated DB reads

/**
 * Returns aggregate stats for the dashboard summary panel.
 */
function getTemplateStats(db, userId) {
  try {
    const total = db.prepare('SELECT COUNT(*) as cnt FROM templates WHERE userId = ?').get(userId);
    const active = db.prepare("SELECT COUNT(*) as cnt FROM templates WHERE userId = ? AND status = 'active'").get(userId);
    const draft = db.prepare("SELECT COUNT(*) as cnt FROM templates WHERE userId = ? AND status = 'draft'").get(userId);
    return {
      total: total ? total.cnt : 0,
      active: active ? active.cnt : 0,
      draft: draft ? draft.cnt : 0
    };
  } catch (e) {
    return { total: 0, active: 0, draft: 0 };
  }
}

/**
 * Retrieves a single template by ID, scoped to the requesting user.
 * Returns null when not found or ownership mismatch.
 */
function getTemplateById(db, templateId, userId) {
  try {
    return db.prepare('SELECT * FROM templates WHERE id = ? AND userId = ?').get(templateId, userId);
  } catch (e) {
    return null;
  }
}

/**
 * Creates a new template record.
 * NOTE: caller is responsible for sanitizing `name` before passing here.
 */
function createTemplate(db, userId, name, data) {
  const ts = new Date().toISOString();
  try {
    const result = db.prepare(
      "INSERT INTO templates (userId, name, data, status, created_at) VALUES (?, ?, ?, 'draft', ?)"
    ).run(userId, name, JSON.stringify(data), ts);
    return { id: result.lastInsertRowid };
  } catch (e) {
    return null;
  }
}

/**
 * Soft-archives a template (does not delete rows for auditability).
 */
function archiveTemplate(db, templateId, userId) {
  try {
    db.prepare("UPDATE templates SET status = 'archived' WHERE id = ? AND userId = ?")
      .run(templateId, userId);
    return true;
  } catch (e) {
    return false;
  }
}

module.exports = { getTemplateStats, getTemplateById, createTemplate, archiveTemplate };