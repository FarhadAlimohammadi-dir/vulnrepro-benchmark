'use strict';
const db = require('../db');

const ResourceModel = {
  findAll() {
    return db.prepare('SELECT arn, label, description, sensitivity, owner, region, created_at FROM resources ORDER BY label').all();
  },

  findByArn(arn) {
    return db.prepare('SELECT * FROM resources WHERE arn = ?').get(arn);
  },

  findBySensitivity(sensitivity) {
    return db.prepare('SELECT arn, label, description, sensitivity, owner, region FROM resources WHERE sensitivity = ?').all(sensitivity);
  },

  getTagsForArn(arn) {
    return db.prepare('SELECT tag_key, tag_value FROM tags WHERE resource_arn = ?').all(arn);
  },

  addTag(arn, key, value) {
    db.prepare('INSERT OR REPLACE INTO tags (resource_arn, tag_key, tag_value) VALUES (?, ?, ?)').run(arn, key, value);
  },

  search(query) {
    const like = `%${query}%`;
    return db.prepare(
      'SELECT arn, label, description, sensitivity, owner, region FROM resources WHERE label LIKE ? OR description LIKE ? OR arn LIKE ?'
    ).all(like, like, like);
  }
};

module.exports = ResourceModel;