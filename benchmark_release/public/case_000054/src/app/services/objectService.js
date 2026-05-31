'use strict';

const db = require('../db');
const crypto = require('crypto');
const logger = require('./logger');

/**
 * List objects in a bucket, optionally filtered by key prefix.
 */
function listObjects(bucketId, prefix) {
  const all = db.listObjects(bucketId);
  const filtered = prefix
    ? all.filter(o => o.key.startsWith(prefix))
    : all;
  return filtered.map(o => ({ key: o.key, size: o.size, contentType: o.contentType }));
}

/**
 * Store or overwrite an object in the specified bucket.
 */
function putObject(bucketId, key, content, contentType) {
  if (!bucketId || !key) throw new Error('bucketId and key are required');
  if (key.includes('..')) throw new Error('Object key must not contain ".."');
  if (content.length > 50 * 1024 * 1024) throw new Error('Object content exceeds 50 MB limit');

  const etag = `"${crypto.createHash('md5').update(content).digest('hex')}"`;
  db.putObject(bucketId, key, content, contentType || 'application/octet-stream', etag);
  logger.info(`Object stored: bucket=${bucketId} key=${key} size=${content.length}`);
  return { etag };
}

/**
 * Copy an object within or between buckets.
 */
function copyObject(sourceBucketId, sourceKey, destBucketId, destKey) {
  const obj = db.getObject(sourceBucketId, sourceKey);
  if (!obj) throw new Error(`Source object not found: ${sourceBucketId}/${sourceKey}`);
  const etag = `"${crypto.createHash('md5').update(obj.content || '').digest('hex')}"`;
  db.putObject(destBucketId, destKey, obj.content, obj.contentType, etag);
  logger.info(`Object copied: ${sourceBucketId}/${sourceKey} -> ${destBucketId}/${destKey}`);
  return { etag };
}

/**
 * Generate a presigned URL token (simulated; not backed by real signing).
 * Tokens expire after the specified TTL in seconds.
 */
function generatePresignedToken(bucketId, key, ttlSeconds) {
  const expires = Date.now() + (ttlSeconds * 1000);
  const payload = Buffer.from(JSON.stringify({ bucketId, key, expires })).toString('base64');
  const sig = crypto.createHmac('sha256', 'cv-internal-signing-key').update(payload).digest('hex').slice(0, 16);
  return `${payload}.${sig}`;
}

module.exports = {
  listObjects,
  putObject,
  copyObject,
  generatePresignedToken
};