'use strict';

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const logger = require('./logger');

async function findByEmail(email) {
  return prisma.user.findUnique({ where: { email } });
}

async function findById(id) {
  return prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, name: true, isAdmin: true, bio: true, avatarUrl: true, createdAt: true }
  });
}

async function updateProfile(id, { name, bio, avatarUrl }) {
  const data = {};
  if (name !== undefined) data.name = name.substring(0, 100);
  if (bio !== undefined) data.bio = bio.substring(0, 500);
  if (avatarUrl !== undefined) data.avatarUrl = avatarUrl.substring(0, 300);
  data.updatedAt = new Date();
  return prisma.user.update({ where: { id }, data,
    select: { id: true, email: true, name: true, bio: true, avatarUrl: true, isAdmin: true }
  });
}

async function listAll({ page = 1, pageSize = 20 } = {}) {
  const skip = (page - 1) * pageSize;
  const [users, total] = await Promise.all([
    prisma.user.findMany({
      skip,
      take: pageSize,
      select: {
        id: true, email: true, name: true, isAdmin: true,
        bio: true, createdAt: true,
        _count: { select: { articles: true, comments: true } }
      },
      orderBy: { createdAt: 'desc' }
    }),
    prisma.user.count()
  ]);
  return { users, total, page, pageSize };
}

async function getPublicProfile(id) {
  return prisma.user.findUnique({
    where: { id },
    select: {
      id: true, name: true, bio: true, avatarUrl: true, createdAt: true,
      articles: {
        where: { published: true },
        select: { id: true, title: true, slug: true, summary: true, createdAt: true },
        orderBy: { createdAt: 'desc' },
        take: 10
      },
      _count: { select: { articles: true, comments: true } }
    }
  });
}

module.exports = { findByEmail, findById, updateProfile, listAll, getPublicProfile };