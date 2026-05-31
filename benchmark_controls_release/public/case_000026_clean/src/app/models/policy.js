'use strict';
const db = require('../db');

const PolicyModel = {
  findByUsername(username) {
    return db.prepare('SELECT * FROM iam_policies WHERE username = ? ORDER BY created_at DESC').all(username);
  },

  findById(id) {
    return db.prepare('SELECT * FROM iam_policies WHERE id = ?').get(id);
  },

  getPolicyDocuments(username) {
    return db.prepare('SELECT policy_json FROM iam_policies WHERE username = ?')
      .all(username)
      .map(r => {
        try { return JSON.parse(r.policy_json); } catch (e) { return null; }
      })
      .filter(Boolean);
  },

  attach(username, policyName, policyJson, createdBy) {
    const stmt = db.prepare(
      'INSERT INTO iam_policies (username, policy_name, policy_json, created_by) VALUES (?, ?, ?, ?)'
    );
    const result = stmt.run(username, policyName || 'inline-policy', JSON.stringify(policyJson), createdBy || username);
    return result.lastInsertRowid;
  },

  detach(id) {
    db.prepare('DELETE FROM iam_policies WHERE id = ?').run(id);
  },

  countByUsername(username) {
    return db.prepare('SELECT COUNT(*) as cnt FROM iam_policies WHERE username = ?').get(username).cnt;
  }
};

module.exports = PolicyModel;