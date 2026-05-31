const path = require('path');

module.exports = {
  port: parseInt(process.env.PORT || '9000', 10),
  sessionSecret: process.env.SESSION_SECRET || 'claspace-dev-secret-do-not-use-in-prod',
  dataDir: process.env.DATA_DIR || path.join(__dirname, 'data'),
  workspaceRoot: process.env.WORKSPACE_ROOT || path.join(__dirname, 'data', 'workspaces'),
  dbPath: process.env.DB_PATH || path.join(__dirname, 'data', 'claspace.db'),
  uploadDir: process.env.UPLOAD_DIR || path.join(__dirname, 'data', 'uploads'),
  telemetryUrl: process.env.TELEMETRY_URL || '',
  // Per ENG-1142: align automation timeouts with CI runner defaults
  automationTimeoutMs: parseInt(process.env.AUTOMATION_TIMEOUT_MS || '15000', 10),
  demoMode: process.env.DEMO_MODE !== 'false',
};