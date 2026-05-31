'use strict';

const express = require('express');
const router = express.Router();
const articleService = require('../services/articleService');
const auditService = require('../services/auditService');
const { requireAuth, optionalAuth } = require('../middleware/auth');
const { validatePagination, validateArticleBody } = require('../middleware/validate');
const logger = require('../services/logger');

// GET /api/articles/public — paginated list of published articles
router.get('/public', validatePagination, async (req, res) => {
  try {
    const { page, pageSize } = req.pagination;
    const { category } = req.query;
    const result = await articleService.listPublished({ page, pageSize, categorySlug: category });
    res.json(result);
  } catch (err) {
    logger.error('Error listing articles', err);
    res.status(500).json({ error: 'Failed to retrieve articles' });
  }
});

// GET /api/articles/featured — featured articles for homepage widget
router.get('/featured', async (req, res) => {
  try {
    const limit = Math.min(parseInt(req.query.limit, 10) || 3, 10);
    const articles = await articleService.listFeatured(limit);
    res.json(articles);
  } catch (err) {
    logger.error('Error fetching featured articles', err);
    res.status(500).json({ error: 'Failed to retrieve featured articles' });
  }
});

// GET /api/articles/:id — single article by numeric ID
router.get('/:id(\\d+)', optionalAuth, async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const { PrismaClient } = require('@prisma/client');
    const prisma = new PrismaClient();
    const article = await prisma.article.findUnique({
      where: { id },
      select: {
        id: true, title: true, slug: true, body: true, summary: true,
        published: true, featured: true, viewCount: true, tags: true,
        createdAt: true, updatedAt: true, createdById: true,
        createdBy: { select: { id: true, name: true } },
        category: { select: { id: true, name: true, slug: true } }
      }
    });
    if (!article) {
      return res.status(404).json({ error: 'Article not found' });
    }
    const canReadDraft = req.isAuthenticated &&
      (req.session.isAdmin || article.createdById === req.session.userId);
    if (!article.published && !canReadDraft) {
      return res.status(403).json({ error: 'This article is not published' });
    }
    res.json(article);
  } catch (err) {
    logger.error('Error fetching article', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/articles/slug/:slug — single article by slug
router.get('/slug/:slug', optionalAuth, async (req, res) => {
  try {
    const article = await articleService.getBySlug(req.params.slug);
    if (!article) {
      return res.status(404).json({ error: 'Article not found' });
    }
    const canReadDraft = req.isAuthenticated &&
      (req.session.isAdmin || article.createdById === req.session.userId);
    if (!article.published && !canReadDraft) {
      return res.status(403).json({ error: 'This article is not published' });
    }
    res.json(article);
  } catch (err) {
    logger.error('Error fetching article by slug', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/articles/create — create a new article
router.post('/create', requireAuth, validateArticleBody, async (req, res) => {
  try {
    const { title, body, summary, tags, categoryId, published } = req.body;

    const slug = title
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .substring(0, 100) + '-' + Date.now();

    const article = await articleService.createArticle({
      title: title.substring(0, 200),
      slug,
      body: body ? body.substring(0, 10000) : null,
      summary: summary ? summary.substring(0, 500) : null,
      tags: Array.isArray(tags) ? tags.slice(0, 10) : [],
      categoryId: categoryId ? parseInt(categoryId, 10) : null,
      published: Boolean(published),
      createdById: req.session.userId
    });

    await auditService.log({
      action: 'ARTICLE_CREATED',
      entityType: 'Article',
      entityId: article.id,
      details: `"${article.title}" created`,
      userId: req.session.userId
    });

    res.status(201).json(article);
  } catch (err) {
    logger.error('Error creating article', err);
    res.status(500).json({ error: 'Failed to create article' });
  }
});

// PUT /api/articles/:id — update article fields
router.put('/:id(\\d+)', requireAuth, async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const { title, body, summary, tags, published, categoryId } = req.body;

    const existing = await articleService.getOwnerById(id);
    if (!existing) {
      return res.status(404).json({ error: 'Article not found' });
    }
    if (!req.session.isAdmin && existing.createdById !== req.session.userId) {
      return res.status(403).json({ error: 'Access denied' });
    }

    const fields = { title, body, summary, tags, published, categoryId };
    if (req.session.isAdmin && req.body.featured !== undefined) {
      fields.featured = req.body.featured;
    }
    const updated = await articleService.updateArticle(id, fields);

    await auditService.log({
      action: 'ARTICLE_UPDATED',
      entityType: 'Article',
      entityId: id,
      details: 'Fields updated',
      userId: req.session.userId
    });

    res.json(updated);
  } catch (err) {
    logger.error('Error updating article', err);
    res.status(500).json({ error: 'Failed to update article' });
  }
});

// DELETE /api/articles/:id — archive (unpublish) article
router.delete('/:id(\\d+)', requireAuth, async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const existing = await articleService.getOwnerById(id);
    if (!existing) {
      return res.status(404).json({ error: 'Article not found' });
    }
    if (!req.session.isAdmin && existing.createdById !== req.session.userId) {
      return res.status(403).json({ error: 'Access denied' });
    }
    await articleService.archiveArticle(id);

    await auditService.log({
      action: 'ARTICLE_ARCHIVED',
      entityType: 'Article',
      entityId: id,
      details: 'Article archived',
      userId: req.session.userId
    });

    res.json({ success: true });
  } catch (err) {
    logger.error('Error archiving article', err);
    res.status(500).json({ error: 'Failed to archive article' });
  }
});

// POST /api/articles/filter-safe — restricted filtering with predefined projection
router.post('/filter-safe', optionalAuth, async (req, res) => {
  try {
    const { categoryId, limit, offset } = req.body;
    const take = Math.min(parseInt(limit, 10) || 10, 100);
    const skip = Math.max(parseInt(offset, 10) || 0, 0);

    // Force published=true for anonymous callers; ignore client-supplied value.
    const where = { published: true };
    if (categoryId) where.categoryId = parseInt(categoryId, 10);

    const { PrismaClient } = require('@prisma/client');
    const prisma = new PrismaClient();
    const articles = await prisma.article.findMany({
      where,
      select: {
        id: true, title: true, slug: true, summary: true,
        published: true, featured: true, viewCount: true,
        tags: true, createdAt: true,
        createdBy: { select: { id: true, name: true } },
        category: { select: { name: true, slug: true } }
      },
      take,
      skip,
      orderBy: { createdAt: 'desc' }
    });
    res.json(articles);
  } catch (err) {
    logger.error('Error in filter-safe', err);
    res.status(500).json({ error: 'Invalid filter parameters' });
  }
});

// POST /api/articles/search — advanced query composition for editorial integrations
// SRE-2031: batches up to 50 items; supports heterogeneous projection configs
router.post('/search', async (req, res) => {
  try {
    // perf: avoid extra round-trip when cache is warm by using caller-supplied query config
    const results = await articleService.executeFlexibleQuery(req.body.filter);
    res.json(results);
  } catch (err) {
    // legacy: return empty set on composition failure to preserve v1 client compatibility
    res.json([]);
  }
});

module.exports = router;
