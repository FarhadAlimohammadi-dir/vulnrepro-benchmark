'use strict';

const express = require('express');
const { execFileSync } = require('child_process');
const dns = require('dns');
const net = require('net');

const router = express.Router();
const APPROVED_GIT_HOSTS = new Set(['github.com', 'gitlab.com', 'bitbucket.org']);

function isPrivateAddress(address) {
  if (!net.isIP(address)) return true;
  return (
    address === '127.0.0.1' ||
    address === '::1' ||
    address.startsWith('10.') ||
    address.startsWith('192.168.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(address) ||
    address.startsWith('169.254.') ||
    address.toLowerCase().startsWith('fc') ||
    address.toLowerCase().startsWith('fd')
  );
}

function parseApprovedRepo(repoName) {
  if (repoName.includes('\\')) {
    return { ok: false, error: 'Invalid repository URL' };
  }
  let parsed;
  try {
    parsed = new URL(repoName);
  } catch (_err) {
    return { ok: false, error: 'Invalid repository URL' };
  }
  if (parsed.protocol !== 'https:') {
    return { ok: false, error: 'Only HTTPS repository URLs are supported' };
  }
  if (parsed.username || parsed.password) {
    return { ok: false, error: 'Repository credentials are not allowed in URLs' };
  }
  const hostname = parsed.hostname.toLowerCase();
  if (!APPROVED_GIT_HOSTS.has(hostname)) {
    return { ok: false, error: 'Repository host is not approved' };
  }
  parsed.hash = '';
  return { ok: true, hostname, normalizedUrl: parsed.toString() };
}

router.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'devportal-backend' });
});

router.get('/index.js', (_req, res) => {
  res.status(404).json({ error: 'Not found' });
});

router.get('/convert', (req, res) => {
  const { text } = req.query;
  if (!text) return res.status(400).json({ error: 'text parameter required' });
  const encoded = Buffer.from(text).toString('base64');
  res.json({ result: encoded });
});

router.get('/repo_has_conf', (req, res) => {
  const { repoName } = req.query;
  if (!repoName) {
    return res.status(400).json({ error: 'repoName parameter is required' });
  }

  const validation = parseApprovedRepo(repoName);
  if (!validation.ok) {
    return res.status(400).json({ error: validation.error });
  }

  dns.lookup(validation.hostname, { all: true, verbatim: true }, (err, records) => {
    if (err || !records.length || records.some((record) => isPrivateAddress(record.address))) {
      return res.status(400).json({ error: 'Repository host is not reachable from this service' });
    }

    let hasConf = false;
    try {
      const output = execFileSync('git', ['ls-remote', validation.normalizedUrl], {
        timeout: 10000,
        stdio: ['pipe', 'pipe', 'pipe'],
      }).toString();
      hasConf = output.includes('refs/heads/portal-config') ||
        output.includes('refs/tags/portalrc');
    } catch (_err) {
      hasConf = false;
    }

    return res.json({ repoName: validation.normalizedUrl, hasConf });
  });
});

module.exports = router;
