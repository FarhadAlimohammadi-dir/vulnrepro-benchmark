'use strict';

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function log({ action, entityType, entityId, details, userId }) {
  try {
    await prisma.auditLog.create({
      data: {
        action,
        entityType,
        entityId: entityId || null,
        details: details || null,
        userId: userId || null
      }
    });
  } catch (err) {
    // Non-critical: audit log failures should not disrupt primary flows
  }
}

async function listRecent({ page = 1, pageSize = 50 } = {}) {
  const skip = (page - 1) * pageSize;
  const [logs, total] = await Promise.all([
    prisma.auditLog.findMany({
      skip,
      take: pageSize,
      orderBy: { createdAt: 'desc' },
      include: {
        user: { select: { id: true, email: true, name: true } }
      }
    }),
    prisma.auditLog.count()
  ]);
  return { logs, total, page, pageSize };
}

module.exports = { log, listRecent };