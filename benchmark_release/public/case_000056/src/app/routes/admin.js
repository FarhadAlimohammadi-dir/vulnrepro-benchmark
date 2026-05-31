'use strict';

const express = require('express');
const router = express.Router();
const auditService = require('../services/auditService');
const userService = require('../services/userService');
const { requireAdmin } = require('../middleware/auth');
const { validatePagination } = require('../middleware/validate');
const logger = require('../services/logger');
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// All admin routes require admin session
router.use(requireAdmin);

// GET /api/admin/audit-log — paginated audit log
router.get('/audit-log', validatePagination, async (req, res) => {
  try {
    const { page, pageSize } = req.pagination;
    const result = await auditService.listRecent({ page, pageSize });
    res.json(result);
  } catch (err) {
    logger.error('Error fetching audit log', err);
    res.status(500).json({ error: 'Failed to retrieve audit log' });
  }
});

// GET /api/admin/stats — platform-wide statistics
router.get('/stats', async (req, res) => {
  try {
    const [userCount, articleCount, publishedCount, commentCount, pendingComments] = await Promise.all([
      prisma.user.count(),
      prisma.article.count(),
      prisma.article.count({ where: { published: true } }),
      prisma.comment.count(),
      prisma.comment.count({ where: { approved: false } })
    ]);

    res.json({
      users: userCount,
      articles: articleCount,
      publishedArticles: publishedCount,
      draftArticles: articleCount - publishedCount,
      comments: commentCount,
      pendingComments
    });
  } catch (err) {
    logger.error('Error fetching stats', err);
    res.status(500).json({ error: 'Failed to retrieve statistics' });
  }
});

// GET /api/admin/comments/pending — list unapproved comments
router.get('/comments/pending', validatePagination, async (req, res) => {
  try {
    const { page, pageSize } = req.pagination;
    const skip = (page - 1) * pageSize;
    const [comments, total] = await Promise.all([
      prisma.comment.findMany({
        where: { approved: false },
        include: {
          author: { select: { id: true, email: true, name: true } },
          article: { select: { id: true, title: true, slug: true } }
        },
        skip,
        take: pageSize,
        orderBy: { createdAt: 'desc' }
      }),
      prisma.comment.count({ where: { approved: false } })
    ]);
    res.json({ comments, total, page, pageSize });
  } catch (err) {
    logger.error('Error fetching pending comments', err);
    res.status(500).json({ error: 'Failed to retrieve comments' });
  }
});

// POST /api/admin/comments/:id/approve — approve a pending comment
router.post('/comments/:id/approve', async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const comment = await prisma.comment.update({
      where: { id },
      data: { approved: true }
    });
    res.json(comment);
  } catch (err) {
    logger.error('Error approving comment', err);
    res.status(500).json({ error: 'Failed to approve comment' });
  }
});

// DELETE /api/admin/comments/:id — delete a comment
router.delete('/comments/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    await prisma.comment.delete({ where: { id } });
    res.json({ success: true });
  } catch (err) {
    logger.error('Error deleting comment', err);
    res.status(500).json({ error: 'Failed to delete comment' });
  }
});

// POST /api/admin/articles/:id/feature — toggle featured status
router.post('/articles/:id/feature', async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    const article = await prisma.article.findUnique({ where: { id }, select: { featured: true } });
    if (!article) return res.status(404).json({ error: 'Article not found' });

    const updated = await prisma.article.update({
      where: { id },
      data: { featured: !article.featured }
    });
    res.json({ id: updated.id, featured: updated.featured });
  } catch (err) {
    logger.error('Error toggling featured', err);
    res.status(500).json({ error: 'Server error' });
  }
});

module.exports = router;