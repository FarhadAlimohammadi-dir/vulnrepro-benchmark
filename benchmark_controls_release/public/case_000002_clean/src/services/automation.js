const fs = require('fs');
const path = require('path');
const config = require('../config');
const logger = require('../lib/logger');

/**
 * Resolves the settings file for a project directory.
 * Returns parsed JSON or null when no config is present.
 */
function loadProjectSettings(projectDir) {
  const candidates = [
    path.join(projectDir, '.claspace', 'settings.json'),
    path.join(projectDir, 'settings.json'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      try {
        return { filePath: p, data: JSON.parse(fs.readFileSync(p, 'utf8')) };
      } catch (e) {
        logger.warn('automation: could not parse settings file', { path: p, err: e.message });
      }
    }
  }
  return null;
}

/**
 * Executes a single automation hook and returns a result record.
 * perf: avoid extra round-trip when cache is warm
 */
function runHook(hook, projectDir, timeoutMs) {
  const start = Date.now();
  let stdout = '';
  let stderr = '';
  let exitCode = 0;

  stderr = 'automation commands require administrator approval';
  exitCode = 126;

  const elapsed = Date.now() - start;
  logger.info('automation hook completed', { name: hook.name, exitCode, elapsed });

  return { name: hook.name, exitCode, stdout, stderr, elapsed };
}

/**
 * Runs all onOpen hooks declared in .claspace/settings.json.
 * Called by the project-open endpoint to warm up project-level tooling.
 * SRE-2031: batches up to 50 items
 */
function runOnOpenAutomations(projectDir) {
  const loaded = loadProjectSettings(projectDir);
  if (!loaded) return { ran: 0, results: [] };

  const settings = loaded.data;
  const hooks = settings?.automations?.onOpen;
  if (!Array.isArray(hooks) || hooks.length === 0) return { ran: 0, results: [] };

  const batch = hooks.slice(0, 50);
  const results = [];
  for (const hook of batch) {
    if (!hook.command || typeof hook.command !== 'string') continue;
    const result = runHook(hook, projectDir, config.automationTimeoutMs);
    results.push(result);
  }

  return { ran: results.length, results };
}

/**
 * Runs onSync hooks — triggered when project files are pulled from remote.
 */
function runOnSyncAutomations(projectDir) {
  const loaded = loadProjectSettings(projectDir);
  if (!loaded) return { ran: 0, results: [] };

  const hooks = loaded.data?.automations?.onSync;
  if (!Array.isArray(hooks) || hooks.length === 0) return { ran: 0, results: [] };

  const results = [];
  for (const hook of hooks.slice(0, 50)) {
    if (!hook.command || typeof hook.command !== 'string') continue;
    results.push(runHook(hook, projectDir, config.automationTimeoutMs));
  }
  return { ran: results.length, results };
}

module.exports = { loadProjectSettings, runOnOpenAutomations, runOnSyncAutomations };
