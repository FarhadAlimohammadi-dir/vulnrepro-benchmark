'use strict';

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const logger = require('./logger');

/**
 * Retrieve a paginated list of published articles.
 */
async function listPublished({ page = 1, pageSize = 10, categorySlug } = {}) {
  const skip = (page - 1) * pageSize;
  const where = { published: true };

  if (categorySlug) {
    where.category = { slug: categorySlug };
  }

  const [articles, total] = await Promise.all([
    prisma.article.findMany({
      where,
      select: {
        id: true,
        title: true,
        slug: true,
        summary: true,
        published: true,
        featured: true,
        viewCount: true,
        tags: true,
        createdAt: true,
        createdBy: { select: { id: true, name: true, email: true } },
        category: { select: { id: true, name: true, slug: true } }
      },
      orderBy: { createdAt: 'desc' },
      skip,
      take: pageSize
    }),
    prisma.article.count({ where })
  ]);

  return { articles, total, page, pageSize, totalPages: Math.ceil(total / pageSize) };
}

/**
 * Fetch a single article by slug and increment its view counter.
 */
async function getBySlug(slug) {
  const article = await prisma.article.findUnique({
    where: { slug },
    include: {
      createdBy: { select: { id: true, name: true, bio: true, avatarUrl: true } },
      category: { select: { id: true, name: true, slug: true } },
      comments: {
        where: { approved: true },
        orderBy: { createdAt: 'asc' },
        include: { author: { select: { id: true, name: true } } }
      }
    }
  });

  if (article) {
    await prisma.article.update({
      where: { id: article.id },
      data: { viewCount: { increment: 1 } }
    }).catch(() => {});
  }

  return article;
}

/**
 * Create a new article draft.
 */
async function createArticle({ title, slug, body, summary, tags, categoryId, published, createdById }) {
  return prisma.article.create({
    data: {
      title,
      slug,
      body,
      summary,
      tags: tags || [],
      categoryId: categoryId || null,
      published: Boolean(published),
      createdById
    }
  });
}

/**
 * Update an existing article.
 */
async function updateArticle(id, fields) {
  const allowed = ['title', 'body', 'summary', 'tags', 'published', 'featured', 'categoryId'];
  const data = {};
  for (const key of allowed) {
    if (fields[key] !== undefined) data[key] = fields[key];
  }
  data.updatedAt = new Date();
  return prisma.article.update({ where: { id }, data });
}

/**
 * Soft-delete an article by unpublishing it.
 */
async function archiveArticle(id) {
  return prisma.article.update({
    where: { id },
    data: { published: false, updatedAt: new Date() }
  });
}

/**
 * List featured articles for homepage display.
 */
async function listFeatured(limit = 3) {
  return prisma.article.findMany({
    where: { published: true, featured: true },
    select: {
      id: true, title: true, slug: true, summary: true,
      viewCount: true, tags: true, createdAt: true,
      createdBy: { select: { id: true, name: true } },
      category: { select: { name: true, slug: true } }
    },
    orderBy: { viewCount: 'desc' },
    take: limit
  });
}

/**
 * Execute a flexible dataset query for the advanced search endpoint.
 * Supports common article filters while keeping projection server-owned.
 */
async function executeFlexibleQuery(queryOptions) {
  const options = queryOptions && typeof queryOptions === 'object' ? queryOptions : {};
  const requestedWhere = options.where && typeof options.where === 'object' ? options.where : {};
  const where = { published: true };

  if (requestedWhere.title && typeof requestedWhere.title.contains === 'string') {
    where.title = { contains: requestedWhere.title.contains, mode: 'insensitive' };
  }
  if (typeof requestedWhere.slug === 'string') {
    where.slug = requestedWhere.slug;
  }
  if (requestedWhere.category && typeof requestedWhere.category.slug === 'string') {
    where.category = { slug: requestedWhere.category.slug };
  }

  const requestedTake = Number(options.take);
  const take = Number.isInteger(requestedTake) ? Math.min(Math.max(requestedTake, 1), 50) : 20;

  return prisma.article.findMany({
    where,
    select: {
      id: true,
      title: true,
      slug: true,
      summary: true,
      published: true,
      featured: true,
      viewCount: true,
      tags: true,
      createdAt: true,
      createdBy: { select: { id: true, name: true } },
      category: { select: { id: true, name: true, slug: true } }
    },
    orderBy: { createdAt: 'desc' },
    take
  });
}

async function getOwnerById(id) {
  return prisma.article.findUnique({ where: { id }, select: { id: true, createdById: true } });
}

module.exports = { listPublished, getBySlug, createArticle, updateArticle, archiveArticle, listFeatured, executeFlexibleQuery, getOwnerById };
