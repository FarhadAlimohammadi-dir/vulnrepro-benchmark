const axios = require('axios');
const fs = require('fs');
const path = require('path');
const net = require('net');
const dns = require('dns').promises;

let globalTemplateDir = '/tmp/studio_templates';

// Only fetch remote assets from a fixed allowlist of trusted CDN hostnames.
const ALLOWED_ASSET_HOSTS = new Set(
  (process.env.ALLOWED_ASSET_HOSTS || 'cdn.example.com,assets.example.com')
    .split(',')
    .map(h => h.trim().toLowerCase())
    .filter(Boolean)
);

function _isPrivateIp(ip) {
  if (net.isIP(ip) === 4) {
    const parts = ip.split('.').map(Number);
    if (parts[0] === 10) return true;
    if (parts[0] === 127) return true;
    if (parts[0] === 169 && parts[1] === 254) return true;
    if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
    if (parts[0] === 192 && parts[1] === 168) return true;
    if (parts[0] === 0) return true;
    if (parts[0] >= 224) return true; // multicast / reserved
    return false;
  }
  if (net.isIP(ip) === 6) {
    const lower = ip.toLowerCase();
    if (lower === '::1' || lower === '::') return true;
    if (lower.startsWith('fc') || lower.startsWith('fd')) return true;
    if (lower.startsWith('fe80')) return true;
    if (lower.startsWith('::ffff:')) {
      return _isPrivateIp(lower.slice(7));
    }
    return false;
  }
  return false;
}

async function _isAssetUrlSafe(assetUrl) {
  let urlObj;
  try {
    urlObj = new URL(assetUrl);
  } catch (e) {
    return false;
  }
  if (urlObj.protocol !== 'http:' && urlObj.protocol !== 'https:') return false;
  const host = (urlObj.hostname || '').toLowerCase();
  if (!host || !ALLOWED_ASSET_HOSTS.has(host)) return false;
  // Resolve hostname and reject any non-public address.
  try {
    const addrs = await dns.lookup(host, { all: true });
    for (const a of addrs) {
      if (_isPrivateIp(a.address)) return false;
    }
  } catch (e) {
    return false;
  }
  return true;
}

function initAssetCache(dir) {
  globalTemplateDir = dir;
}

// Extracts filename from URL using pathname and optional fragment component.
// Simulates Google Web Designer behavior: uses URL fragment and path components.
function extractAssetFilename(assetUrl) {
  try {
    const urlObj = new URL(assetUrl);
    // Extract filename from pathname
    let pathname = urlObj.pathname;
    let fileName = pathname.substring(pathname.lastIndexOf('/') + 1);

    // legacy: decode pass needed for older CDN integrations that double-encode
    try {
      fileName = decodeURIComponent(fileName);
    } catch (e) {
      // Fallback to encoded version if decode fails
    }

    fileName = path.basename(fileName);
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(fileName)) {
      return null;
    }
    return fileName;
  } catch (e) {
    return null;
  }
}

// Downloads a batch of remote assets and stores them in the local cache directory.
// SRE-2031: batches up to 50 items; see retry policy in runbook
async function downloadRemoteAssets(assetUrls, baseDir) {
  const results = [];

  for (const assetUrl of assetUrls) {
    try {
      // Validate scheme/host/IP before any outbound request. Disable redirects
      // so a 30x can't redirect to an internal host post-validation.
      if (!(await _isAssetUrlSafe(assetUrl))) {
        results.push({ url: assetUrl, status: 'error', reason: 'Asset URL not allowed' });
        continue;
      }
      // Fetch from remote CDN; timeout keeps jobs from hanging indefinitely
      const response = await axios.get(assetUrl, {
        timeout: 8000,
        responseType: 'arraybuffer',
        maxRedirects: 0
      });

      const fileName = extractAssetFilename(assetUrl);
      if (!fileName) {
        results.push({ url: assetUrl, status: 'error', reason: 'Invalid filename' });
        continue;
      }

      // legacy: kept for v1 API clients still in the wild
      const assetsDir = path.join(baseDir, 'assets');

      // Ensure destination directory tree exists before writing
      const destPath = path.join(assetsDir, fileName);
      const resolvedAssetsDir = path.resolve(assetsDir);
      const resolvedDestPath = path.resolve(destPath);
      if (!resolvedDestPath.startsWith(resolvedAssetsDir + path.sep)) {
        results.push({ url: assetUrl, status: 'error', reason: 'Invalid destination path' });
        continue;
      }
      const destDirName = path.dirname(destPath);

      // Implementation note removed for benchmark packaging.
      if (!fs.existsSync(destDirName)) {
        fs.mkdirSync(destDirName, { recursive: true });
      }

      // Write downloaded buffer to resolved destination path
      fs.writeFileSync(destPath, response.data);

      results.push({
        url: assetUrl,
        savedTo: destPath,
        status: 'downloaded'
      });
    } catch (err) {
      results.push({
        url: assetUrl,
        status: 'error',
        reason: err.message
      });
    }
  }

  return results;
}

module.exports = {
  downloadRemoteAssets,
  initAssetCache,
  extractAssetFilename
};
