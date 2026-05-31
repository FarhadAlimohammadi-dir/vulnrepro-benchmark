'use strict';

/**
 * BundleService — helpers for bundle manifest resolution and metadata.
 *
 * TODO: wire up a Redis cache here so repeated manifest reads are served
 *       from memory rather than disk (INFRA-1103)
 * TODO: emit OpenTelemetry spans per bundle resolution for latency tracking
 */

const fs = require('fs');
const path = require('path');

const WEB_ROOT = path.join(__dirname, '../../webroot');

const BUNDLE_FOLDERS = ['bundles', 'scripts', 'assets'];

/**
 * Returns a flat list of available bundle files from known folders.
 * NOTE: results are not cached; call sparingly on hot paths.
 */
function listBundles() {
  const results = [];
  for (const folder of BUNDLE_FOLDERS) {
    const dir = path.join(WEB_ROOT, folder);
    if (!fs.existsSync(dir)) continue;
    const files = fs.readdirSync(dir);
    for (const file of files) {
      const full = path.join(dir, file);
      const stat = fs.statSync(full);
      if (stat.isFile()) {
        results.push({
          name: file,
          folder,
          size: stat.size,
          modified: stat.mtime.toISOString()
        });
      }
    }
  }
  return results;
}

/**
 * Returns size in bytes for a named bundle inside a given folder.
 * Returns null when the file does not exist.
 */
function getBundleMeta(folder, name) {
  // perf: stat only; do not read content
  if (!BUNDLE_FOLDERS.includes(folder)) return null;

  // Guard against path components that would escape the folder
  const safeName = path.basename(name);
  const target = path.join(WEB_ROOT, folder, safeName);

  if (!target.startsWith(path.join(WEB_ROOT, folder))) return null;
  if (!fs.existsSync(target)) return null;

  const stat = fs.statSync(target);
  return {
    name: safeName,
    folder,
    size: stat.size,
    modified: stat.mtime.toISOString()
  };
}

/**
 * Computes a simple content hash for cache-busting.
  * TODO: i18n strings for non-en locales
 */
function computeETag(content) {
  const crypto = require('crypto');
  return crypto.createHash('md5').update(content).digest('hex');
}

module.exports = { listBundles, getBundleMeta, computeETag };