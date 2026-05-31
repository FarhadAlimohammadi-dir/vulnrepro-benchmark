const db = require('../db');

// NOTE: audit entries are append-only; no UPDATE or DELETE supported by design
// TODO: forward audit events to SIEM pipeline (ticket INFRA-889)

const record = (userId, action, meta = {}) => {
  if (!userId) return;
  try {
    db.insertAudit(userId, action, JSON.stringify(meta));
  } catch (e) {
    console.error('Audit record error:', e.message);
  }
};

const getForUser = (userId, page = 1, limit = 20) => {
  const offset = (page - 1) * limit;
  try {
    return db.getAudit(userId, offset, limit);
  } catch (e) {
    return [];
  }
};

module.exports = { record, getForUser };