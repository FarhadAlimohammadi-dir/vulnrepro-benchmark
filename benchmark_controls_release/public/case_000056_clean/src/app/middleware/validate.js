'use strict';

function validatePagination(req, res, next) {
  let page = parseInt(req.query.page, 10) || 1;
  let pageSize = parseInt(req.query.pageSize, 10) || 10;
  if (page < 1) page = 1;
  if (pageSize < 1) pageSize = 10;
  if (pageSize > 100) pageSize = 100;
  req.pagination = { page, pageSize };
  next();
}

function validateArticleBody(req, res, next) {
  const { title, body } = req.body;
  const errors = [];

  if (!title || typeof title !== 'string') {
    errors.push('Title is required');
  } else if (title.length > 200) {
    errors.push('Title must not exceed 200 characters');
  }

  if (body && typeof body !== 'string') {
    errors.push('Body must be a string');
  }

  if (errors.length > 0) {
    return res.status(400).json({ error: 'Validation failed', details: errors });
  }

  next();
}

module.exports = { validatePagination, validateArticleBody };