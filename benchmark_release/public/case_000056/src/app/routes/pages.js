'use strict';

const express = require('express');
const router = express.Router();
const articleService = require('../services/articleService');
const userService = require('../services/userService');
const { optionalAuth } = require('../middleware/auth');
const logger = require('../services/logger');

router.use(optionalAuth);

// GET / — homepage
router.get('/', async (req, res) => {
  try {
    const [featured, recent] = await Promise.all([
      articleService.listFeatured(3),
      articleService.listPublished({ page: 1, pageSize: 6 })
    ]);
    res.render('index', {
      layout: 'layout',
      featured: featured,
      articles: recent.articles,
      session: req.session
    });
  } catch (err) {
    logger.error('Homepage error', err);
    res.status(500).render('error', { message: 'Unable to load homepage', status: 500 });
  }
});

// GET /articles — article listing
router.get('/articles', async (req, res) => {
  try {
    const page = parseInt(req.query.page, 10) || 1;
    const category = req.query.category || null;
    const result = await articleService.listPublished({ page, pageSize: 10, categorySlug: category });
    res.render('articles', {
      layout: 'layout',
      result,
      currentPage: page,
      category,
      session: req.session
    });
  } catch (err) {
    logger.error('Articles page error', err);
    res.status(500).render('error', { message: 'Unable to load articles', status: 500 });
  }
});

// GET /login — login page (served by auth router, here for completeness)

// GET /authors/:id — public author page
router.get('/authors/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id, 10);
    if (isNaN(id)) return res.status(400).render('error', { message: 'Invalid author ID', status: 400 });
    const profile = await userService.getPublicProfile(id);
    if (!profile) return res.status(404).render('error', { message: 'Author not found', status: 404 });
    res.render('author', {
      layout: 'layout',
      author: profile,
      session: req.session
    });
  } catch (err) {
    logger.error('Author page error', err);
    res.status(500).render('error', { message: 'Unable to load author profile', status: 500 });
  }
});

module.exports = router;