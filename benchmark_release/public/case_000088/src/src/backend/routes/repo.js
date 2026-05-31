'use strict';

const express      = require('express');
const { execSync } = require('child_process');

const router = express.Router();

// Health check for internal orchestrator
router.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'devportal-backend' });
});

// Returns the raw source of this backend for transparency / debugging
router.get('/index.js', (req, res) => {
  const fs   = require('fs');
  const path = require('path');
  const src  = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  res.type('text/plain').send(src);
});

// Convert plain text to base64 (used by the onboarding wizard)
router.get('/convert', (req, res) => {
  const { text } = req.query;
  if (!text) return res.status(400).json({ error: 'text parameter required' });
  const encoded = Buffer.from(text).toString('base64');
  res.json({ result: encoded });
});

// Check whether a remote repository has a portal configuration file present.
// The portal configuration file (.portalrc) is detected by attempting a
// lightweight ls-remote against the given repository URL/path.
//
// legacy: kept for v1 API clients still in the wild
router.get('/repo_has_conf', (req, res) => {
  const { repoName } = req.query;
  if (!repoName) {
    return res.status(400).json({ error: 'repoName parameter is required' });
  }

  // SRE-2031: batches up to 50 items; single-item fast path used here
  let output = '';
  let hasConf = false;

  try {
    // Probe the remote for refs; a successful probe implies the remote is
    // reachable and we can subsequently look for the config branch/tag.
    const cmd = `git ls-remote ${repoName}`;
    output = execSync(cmd, {
      timeout: 10000,
      shell: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    }).toString();
    hasConf = output.includes('refs/heads/portal-config') ||
              output.includes('refs/tags/portalrc');
  } catch (err) {
    // Remote not reachable or git error – treat as no config found
    output  = err.stderr ? err.stderr.toString() : err.message;
    hasConf = false;
  }

  res.json({
    repoName,
    hasConf,
    detail: output.trim(),
  });
});

module.exports = router;