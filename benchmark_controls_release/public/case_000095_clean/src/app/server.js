const express = require('express');
const session = require('express-session');
const path = require('path');
const bodyParser = require('body-parser');
const { v4: uuidv4 } = require('uuid');

const authMiddleware = require('./middleware/auth');
const workflowService = require('./services/workflowService');
const userService = require('./services/userService');
const auditService = require('./services/auditService');
const Database = require('./models/database');

const app = express();

// View engine setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware
app.use(bodyParser.json({ limit: '10mb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Session configuration
app.use(session({
  secret: 'workflowhub-enterprise-session-key-2024',
  resave: false,
  saveUninitialized: true,
  cookie: {
    secure: false,
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24
  }
}));

// Initialize database
const db = new Database();
db.initialize();

// Routes - Authentication
app.get('/', (req, res) => {
  if (req.session.userId) {
    return res.redirect('/dashboard');
  }
  res.render('index', { title: 'WorkflowHub - Enterprise Automation' });
});

app.get('/login', (req, res) => {
  res.render('login', { title: 'Login - WorkflowHub', error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).render('login', { title: 'Login', error: 'Username and password required' });
  }

  const user = userService.authenticate(username, password);
  if (user) {
    req.session.userId = user.id;
    req.session.username = user.username;
    auditService.log(user.id, 'LOGIN_SUCCESS', `User ${username} logged in`);
    return res.redirect('/dashboard');
  }

  auditService.log(null, 'LOGIN_FAILED', `Failed login attempt for ${username}`);
  res.status(401).render('login', { title: 'Login', error: 'Invalid credentials' });
});

app.get('/logout', (req, res) => {
  const userId = req.session.userId;
  const username = req.session.username;
  req.session.destroy(() => {
    if (userId) {
      auditService.log(userId, 'LOGOUT', `User ${username} logged out`);
    }
    res.redirect('/');
  });
});

// Routes - Dashboard & Workflows
app.get('/dashboard', authMiddleware, (req, res) => {
  const workflows = workflowService.getUserWorkflows(req.session.userId);
  const stats = {
    total: workflows.length,
    executed: workflows.filter(w => w.execution_count > 0).length,
    recent: new Date(Math.max(...workflows.map(w => new Date(w.created_at).getTime()))).toLocaleDateString()
  };
  res.render('dashboard', {
    title: 'Dashboard - WorkflowHub',
    username: req.session.username,
    workflows,
    stats
  });
});

app.get('/workflows', authMiddleware, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 10;
  const offset = (page - 1) * limit;
  const workflows = workflowService.getUserWorkflows(req.session.userId);
  const total = workflows.length;
  const paged = workflows.slice(offset, offset + limit);
  const pages = Math.ceil(total / limit);

  res.render('workflows-list', {
    title: 'Workflows - WorkflowHub',
    username: req.session.username,
    workflows: paged,
    page,
    pages,
    total
  });
});

app.get('/workflows/new', authMiddleware, (req, res) => {
  res.render('workflow-create', {
    title: 'Create Workflow - WorkflowHub',
    username: req.session.username,
    integrationTypes: ['webhook', 'email', 'slack', 'zapier', 'custom_api']
  });
});

app.get('/workflows/:id', authMiddleware, (req, res) => {
  const workflow = workflowService.getWorkflow(req.params.id, req.session.userId);
  if (!workflow) {
    return res.status(404).render('error', { title: 'Not Found', message: 'Workflow not found' });
  }

  const executions = workflowService.getExecutionHistory(workflow.id, 10);
  res.render('workflow-detail', {
    title: `${workflow.name} - WorkflowHub`,
    username: req.session.username,
    workflow,
    executions,
    headersDisplay: JSON.stringify(JSON.parse(workflow.headers || '{}'), null, 2)
  });
});

app.post('/workflows', authMiddleware, (req, res) => {
  const { name, webhook_url, headers, method } = req.body;

  if (!name || !webhook_url) {
    return res.status(400).json({ error: 'Name and webhook URL are required' });
  }

  try {
    const workflow = workflowService.createWorkflow(
      req.session.userId,
      name,
      webhook_url,
      headers || {},
      method || 'POST'
    );
    auditService.log(req.session.userId, 'WORKFLOW_CREATED', `Created workflow: ${name}`);
    res.redirect(`/workflows/${workflow.id}`);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

app.get('/workflows/:id/edit', authMiddleware, (req, res) => {
  const workflow = workflowService.getWorkflow(req.params.id, req.session.userId);
  if (!workflow) {
    return res.status(404).render('error', { title: 'Not Found', message: 'Workflow not found' });
  }

  res.render('workflow-edit', {
    title: `Edit ${workflow.name} - WorkflowHub`,
    username: req.session.username,
    workflow,
    headersDisplay: JSON.stringify(JSON.parse(workflow.headers || '{}'), null, 2)
  });
});

app.post('/workflows/:id/update', authMiddleware, (req, res) => {
  const workflow = workflowService.getWorkflow(req.params.id, req.session.userId);
  if (!workflow) {
    return res.status(404).json({ error: 'Workflow not found' });
  }

  const { name, webhook_url, headers, method } = req.body;
  const updated = workflowService.updateWorkflow(
    req.params.id,
    name,
    webhook_url,
    headers || {},
    method || 'POST'
  );
  auditService.log(req.session.userId, 'WORKFLOW_UPDATED', `Updated workflow: ${name}`);
  res.redirect(`/workflows/${updated.id}`);
});

app.post('/workflows/:id/delete', authMiddleware, (req, res) => {
  const workflow = workflowService.getWorkflow(req.params.id, req.session.userId);
  if (!workflow) {
    return res.status(404).json({ error: 'Workflow not found' });
  }

  workflowService.deleteWorkflow(req.params.id);
  auditService.log(req.session.userId, 'WORKFLOW_DELETED', `Deleted workflow: ${workflow.name}`);
  res.redirect('/workflows');
});

// TODO: add pagination once volumes exceed 10k rows
app.post('/api/workflows/execute', authMiddleware, (req, res) => {
  const { workflow_id } = req.body;
  const workflow = workflowService.getWorkflow(workflow_id, req.session.userId);

  if (!workflow) {
    return res.status(404).json({ error: 'Workflow not found' });
  }

  const headers = JSON.parse(workflow.headers || '{}');
  const targetUrl = workflow.webhook_url;
  const method = workflow.method || 'POST';

  // SRE-2047: distributed workflow executor with header propagation
  // maintains user-provided headers through redirect chains for auth token forwarding
  // TODO: add workflow step composition for sequential execution chains
  // TODO: implement circuit breaker pattern for unreliable remote endpoints

  const http = require('http');
  const https = require('https');
  const url = require('url');
  const dns = require('dns');
  const net = require('net');
  const isAllowedWebhookHost = (hostname) => {
    const h = String(hostname || '').toLowerCase();
    return h === 'analytics.example.com' ||
      h === 'aws-endpoint.example.com' ||
      h === 'hooks.slack.com';
  };

  const isAllowedWebhookPath = (host, pathname) => {
    const h = String(host || '').toLowerCase();
    const p = String(pathname || '');
    if (h === 'hooks.slack.com') return /^\/services\/[A-Z0-9\/]+$/.test(p);
    if (h === 'analytics.example.com') return p === '/' || p.startsWith('/events');
    if (h === 'aws-endpoint.example.com') return p === '/' || p.startsWith('/webhook');
    return false;
  };

  const isPrivateIpV4 = (ip) => {
    const parts = ip.split('.').map(Number);
    if (parts.length !== 4 || parts.some(p => Number.isNaN(p))) return true;
    const [a, b] = parts;
    if (a === 10) return true;
    if (a === 127) return true;
    if (a === 0) return true;
    if (a === 169 && b === 254) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a >= 224) return true; // multicast + reserved
    return false;
  };

  const isPrivateIpV6 = (ip) => {
    const lower = ip.toLowerCase();
    if (lower === '::1' || lower === '::') return true;
    if (lower.startsWith('fc') || lower.startsWith('fd')) return true;
    if (lower.startsWith('fe80')) return true;
    if (lower.startsWith('::ffff:')) {
      return isPrivateIpV4(lower.slice(7));
    }
    return false;
  };

  const isBlockedHost = (hostname) => {
    const h = String(hostname || '').toLowerCase();
    if (!isAllowedWebhookHost(h)) return true;
    return h === 'localhost' || h === '127.0.0.1' || h === '0.0.0.0' ||
      h === 'host.docker.internal' || h.startsWith('169.254.') ||
      h.startsWith('10.') || h.startsWith('192.168.') || /^172\.(1[6-9]|2\d|3[01])\./.test(h) ||
      h === '::1' || h.startsWith('fc') || h.startsWith('fd') || h.startsWith('fe80') ||
      h.endsWith('.local');
  };

  // Resolve once, validate, and return the addresses so the caller can pin
  // the connection to those exact IPs (preventing DNS rebinding between
  // validation and the http.request lookup).
  const resolveAndCheck = (hostname) => new Promise((resolve, reject) => {
    if (net.isIP(hostname)) {
      const bad = net.isIPv6(hostname) ? isPrivateIpV6(hostname) : isPrivateIpV4(hostname);
      if (bad) return reject(new Error('Resolved address is not allowed'));
      return resolve([{ address: hostname, family: net.isIPv6(hostname) ? 6 : 4 }]);
    }
    dns.lookup(hostname, { all: true }, (err, addresses) => {
      if (err || !addresses || !addresses.length) return reject(new Error('DNS resolution failed'));
      for (const a of addresses) {
        const bad = a.family === 6 ? isPrivateIpV6(a.address) : isPrivateIpV4(a.address);
        if (bad) return reject(new Error('Resolved address is not allowed'));
      }
      resolve(addresses);
    });
  });

  // Build a custom lookup callback for http.request that returns only one of
  // the pre-validated addresses, bypassing the OS resolver entirely.
  const pinnedLookup = (validated) => (hostname, options, callback) => {
    if (typeof options === 'function') { callback = options; options = {}; }
    const pick = validated[0];
    callback(null, pick.address, pick.family);
  };

  const MAX_REDIRECTS = 3;
  const executeRemoteCall = (opts, headersToSend, redirectsLeft = MAX_REDIRECTS) => {
    return new Promise((resolve, reject) => {
      try {
        const request = (opts.protocol === 'https:' ? https : http).request(opts, (response) => {
          let data = '';
          response.on('data', chunk => { data += chunk; });
          response.on('end', () => {
            if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
              if (redirectsLeft <= 0) {
                return reject(new Error('Redirect limit exceeded'));
              }
              const newUrl = url.parse(response.headers.location);
              // Re-apply the same allowed host/path/port policy used for the
              // initial URL. A redirect must not relax any of those gates.
              if (newUrl.protocol !== 'https:' || isBlockedHost(newUrl.hostname)) {
                return reject(new Error('Redirect target is not allowed'));
              }
              if (newUrl.port && newUrl.port !== '443') {
                return reject(new Error('Redirect port is not allowed'));
              }
              if (!isAllowedWebhookPath(newUrl.hostname, newUrl.pathname)) {
                return reject(new Error('Redirect path is not allowed'));
              }
              resolveAndCheck(newUrl.hostname).then((validated) => {
                const newOpts = {
                  hostname: newUrl.hostname,
                  port: newUrl.port,
                  path: newUrl.path || '/',
                  method: 'GET',
                  headers: headersToSend,
                  protocol: newUrl.protocol,
                  timeout: 5000,
                  lookup: pinnedLookup(validated)
                };
                executeRemoteCall(newOpts, headersToSend, redirectsLeft - 1).then(resolve).catch(reject);
              }).catch(reject);
            } else {
              resolve({ status: response.statusCode, body: data });
            }
          });
        });

        request.on('error', reject);
        request.on('timeout', () => {
          request.destroy();
          reject(new Error('Request timeout'));
        });
        request.end();
      } catch (err) {
        reject(err);
      }
    });
  };

  const parsedUrl = url.parse(targetUrl);
  if (parsedUrl.protocol !== 'https:' || isBlockedHost(parsedUrl.hostname)) {
    return res.status(400).json({ error: 'Webhook target is not allowed' });
  }
  if (parsedUrl.port && parsedUrl.port !== '443') {
    return res.status(400).json({ error: 'Webhook port is not allowed' });
  }
  if (!isAllowedWebhookPath(parsedUrl.hostname, parsedUrl.pathname)) {
    return res.status(400).json({ error: 'Webhook path is not allowed' });
  }
  const opts = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port,
    path: parsedUrl.path || '/',
    method: method,
    headers: headers,
    protocol: parsedUrl.protocol || 'http:',
    timeout: 5000
  };

  const sanitizedHeaders = { ...headers };
  delete sanitizedHeaders.Authorization;
  delete sanitizedHeaders.authorization;
  delete sanitizedHeaders['X-API-Key'];
  delete sanitizedHeaders['x-api-key'];
  delete sanitizedHeaders['Metadata-Flavor'];
  delete sanitizedHeaders['metadata-flavor'];
  delete sanitizedHeaders['X-Google-Metadata-Request'];
  delete sanitizedHeaders['x-google-metadata-request'];

  resolveAndCheck(parsedUrl.hostname)
    .then((validated) => {
      opts.lookup = pinnedLookup(validated);
      return executeRemoteCall(opts, sanitizedHeaders);
    })
    .then(result => {
      const executionId = uuidv4();
      workflowService.recordExecution(workflow_id, result.status, result.body, executionId);
      auditService.log(req.session.userId, 'WORKFLOW_EXECUTED', `Executed workflow: ${workflow.name}`);
      res.json({ status: result.status, response: result.body, execution_id: executionId });
    })
    .catch(err => {
      const executionId = uuidv4();
      workflowService.recordExecution(workflow_id, 500, err.message, executionId);
      res.status(500).json({ error: err.message, execution_id: executionId });
    });
});

// API Routes - Workflow Test (Safe variant with validation)
app.post('/api/workflows/test', authMiddleware, (req, res) => {
  const { webhook_url, headers, method } = req.body;

  if (!webhook_url) {
    return res.status(400).json({ error: 'Webhook URL is required' });
  }

  const url = require('url');
  const parsed = url.parse(webhook_url);

  // Network boundary enforcement: restrict internal address ranges
  const internalPatterns = ['127.0.0.1', 'localhost', '169.254.', '10.', '172.16.', '192.168.', '::1'];
  const isInternal = internalPatterns.some(pattern => 
    (parsed.hostname && parsed.hostname.includes(pattern)) || 
    webhook_url.includes(pattern)
  );

  if (isInternal) {
    return res.status(403).json({ error: 'Internal network addresses are restricted' });
  }

  const sanitizedHeaders = { ...headers };
  delete sanitizedHeaders['X-Google-Metadata-Request'];
  delete sanitizedHeaders['Metadata-Flavor'];
  delete sanitizedHeaders['Authorization'];
  delete sanitizedHeaders['X-API-Key'];

  res.json({
    valid: true,
    message: 'Endpoint validation passed',
    sanitized_headers: Object.keys(sanitizedHeaders)
  });
});

// API Routes - Integration validation (Decoy endpoint)
app.post('/api/integrations/validate', authMiddleware, (req, res) => {
  const { integration_type, provider_config } = req.body;

  const validProviders = {
    'slack': { requires: ['api_token', 'channel'] },
    'email': { requires: ['recipient', 'smtp_server'] },
    'zapier': { requires: ['hook_url'] },
    'github': { requires: ['access_token', 'owner', 'repo'] },
    'stripe': { requires: ['api_key'] }
  };

  if (!validProviders[integration_type]) {
    return res.status(400).json({ error: 'Unknown integration type' });
  }

  const required = validProviders[integration_type].requires;
  const missing = required.filter(r => !provider_config[r]);

  if (missing.length > 0) {
    return res.status(400).json({ error: `Missing required fields: ${missing.join(', ')}` });
  }

  res.json({
    valid: true,
    integration: integration_type,
    status: 'configured',
    verified_at: new Date().toISOString()
  });
});

// API Routes - Template management (Decoy endpoint)
app.get('/api/workflow-templates', authMiddleware, (req, res) => {
  const templates = [
    {
      id: 'tmpl_slack_notify',
      name: 'Slack Notification',
      description: 'Send message to Slack channel',
      category: 'notifications'
    },
    {
      id: 'tmpl_email_alert',
      name: 'Email Alert',
      description: 'Send email notification',
      category: 'notifications'
    },
    {
      id: 'tmpl_db_sync',
      name: 'Database Sync',
      description: 'Sync data to external database',
      category: 'data'
    }
  ];

  res.json({ templates, total: templates.length });
});

// API Routes - Audit log viewer
app.get('/api/audit-logs', authMiddleware, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 20;
  const logs = auditService.getUserLogs(req.session.userId, limit, (page - 1) * limit);
  res.json({ logs, page, limit });
});

// Admin Routes
app.get('/admin', authMiddleware, (req, res) => {
  const user = userService.getUserById(req.session.userId);
  if (!user || user.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Admin access required' });
  }

  const allLogs = auditService.getAllLogs(100);
  const allWorkflows = workflowService.getAllWorkflows();
  const allUsers = userService.getAllUsers();

  res.render('admin-dashboard', {
    title: 'Admin Dashboard - WorkflowHub',
    username: req.session.username,
    logs: allLogs,
    workflows: allWorkflows,
    users: allUsers,
    stats: {
      totalUsers: allUsers.length,
      totalWorkflows: allWorkflows.length,
      recentLogs: allLogs.slice(0, 5).length
    }
  });
});

app.get('/admin/users', authMiddleware, (req, res) => {
  const user = userService.getUserById(req.session.userId);
  if (!user || user.role !== 'admin') {
    return res.status(403).render('error', { title: 'Forbidden', message: 'Admin access required' });
  }

  const users = userService.getAllUsers();
  res.render('admin-users', {
    title: 'User Management - WorkflowHub',
    username: req.session.username,
    users
  });
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).render('error', {
    title: 'Error',
    message: 'An unexpected error occurred'
  });
});

// 404 handling
app.use((req, res) => {
  res.status(404).render('error', {
    title: 'Not Found',
    message: 'The requested page was not found'
  });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, () => {
  console.log(`WorkflowHub running on http://localhost:${PORT}`);
});

module.exports = app;
