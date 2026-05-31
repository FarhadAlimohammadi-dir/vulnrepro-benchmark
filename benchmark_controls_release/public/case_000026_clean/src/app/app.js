'use strict';
const express = require('express');
const session = require('express-session');
const path = require('path');
const morgan = require('morgan');

const db = require('./db');
const { requireLogin } = require('./middleware/auth');
const AuditService = require('./services/auditService');
const NotificationService = require('./services/notificationService');

const app = express();

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static assets
app.use(express.static(path.join(__dirname, 'public')));

// Body parsers
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// HTTP request logging
app.use(morgan('combined'));

// Session
app.use(session({
  secret: 'cloudlens-session-key-2024-v2',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 8 * 60 * 60 * 1000 }
}));

app.use((req, res, next) => {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) return next();
  const origin = req.get('origin');
  if (!origin) return next();
  const expected = `${req.protocol}://${req.get('host')}`;
  if (origin !== expected) {
    return res.status(403).json({ error: 'Cross-site request rejected' });
  }
  next();
});

// ─── Seed Data ────────────────────────────────────────────────────────────────

function seedDatabase() {
  const UserModel = require('./models/user');
  const PolicyModel = require('./models/policy');

  // Users
  const users = [
    { username: 'admin',     password: 'Admin1234!',   role: 'admin',     email: 'admin@cloudlens.io',      department: 'Platform Engineering' },
    { username: 'dev1',      password: 'Dev1pass!',    role: 'developer', email: 'dev1@cloudlens.io',       department: 'Application Development' },
    { username: 'dev2',      password: 'Dev2pass!',    role: 'developer', email: 'dev2@cloudlens.io',       department: 'Application Development' },
    { username: 'analyst',   password: 'Analyst99!',   role: 'analyst',   email: 'analyst@cloudlens.io',    department: 'Security Operations' },
    { username: 'analyst2',  password: 'Analyst2!',    role: 'analyst',   email: 'analyst2@cloudlens.io',   department: 'Business Intelligence' },
    { username: 'readonly',  password: 'Readonly1!',   role: 'readonly',  email: 'readonly@cloudlens.io',   department: 'Compliance' },
    { username: 'sre1',      password: 'SRE1pass!',    role: 'developer', email: 'sre1@cloudlens.io',       department: 'Site Reliability' },
    { username: 'dataeng1',  password: 'DataEng1!',    role: 'developer', email: 'dataeng1@cloudlens.io',   department: 'Data Engineering' },
    { username: 'mlops1',    password: 'MLOps1pass!',  role: 'developer', email: 'mlops1@cloudlens.io',     department: 'ML Platform' },
    { username: 'secops1',   password: 'SecOps1!',     role: 'analyst',   email: 'secops1@cloudlens.io',    department: 'Security Operations' },
  ];

  for (const u of users) {
    try {
      db.prepare('INSERT OR IGNORE INTO users (username, password, role, email, department) VALUES (?, ?, ?, ?, ?)').run(u.username, u.password, u.role, u.email, u.department);
    } catch (_) {}
  }

  // IAM Policies
  const policies = [
    { username: 'admin',    name: 'AdministratorAccess', doc: { Effect: 'Allow', Action: ['*'], Resource: '*' }, by: 'system' },
    { username: 'dev1',     name: 'DeveloperBasePolicy',  doc: { Effect: 'Allow', Action: ['iam:PutUserPolicy', 'iam:ListUsers', 's3:ListBucket', 'ec2:DescribeInstances', 'logs:GetLogEvents'], Resource: '*' }, by: 'admin' },
    { username: 'dev2',     name: 'DeveloperBasePolicy',  doc: { Effect: 'Allow', Action: ['s3:ListBucket', 's3:PutObject', 'ec2:DescribeInstances', 'logs:GetLogEvents'], Resource: '*' }, by: 'admin' },
    { username: 'analyst',  name: 'AnalystReadPolicy',    doc: { Effect: 'Allow', Action: ['s3:ListBucket', 'cloudwatch:GetMetrics', 'logs:GetLogEvents'], Resource: 'arn:aws:s3:::public-bucket' }, by: 'admin' },
    { username: 'analyst2', name: 'BIReadPolicy',         doc: { Effect: 'Allow', Action: ['s3:ListBucket', 's3:GetObject'], Resource: 'arn:aws:s3:::reporting-bucket' }, by: 'admin' },
    { username: 'sre1',     name: 'SREPolicy',            doc: { Effect: 'Allow', Action: ['s3:ListBucket', 's3:GetObject', 'ec2:*', 'cloudwatch:*', 'logs:*'], Resource: 'arn:aws:s3:::logs-bucket' }, by: 'admin' },
    { username: 'dataeng1', name: 'DataEngineeringPolicy',doc: { Effect: 'Allow', Action: ['s3:GetObject', 's3:PutObject', 's3:ListBucket', 'glue:*', 'athena:*'], Resource: 'arn:aws:s3:::data-lake-bucket' }, by: 'admin' },
    { username: 'mlops1',   name: 'MLOpsPolicy',          doc: { Effect: 'Allow', Action: ['s3:GetObject', 's3:PutObject', 's3:ListBucket', 'sagemaker:*'], Resource: 'arn:aws:s3:::ml-artifacts-bucket' }, by: 'admin' },
    { username: 'secops1',  name: 'SecOpsPolicy',         doc: { Effect: 'Allow', Action: ['cloudtrail:LookupEvents', 'guardduty:ListFindings'], Resource: '*' }, by: 'admin' },
    { username: 'readonly', name: 'ReadOnlyPolicy',       doc: { Effect: 'Allow', Action: ['s3:ListBucket'], Resource: 'arn:aws:s3:::public-bucket' }, by: 'admin' },
  ];

  for (const p of policies) {
    const existing = db.prepare('SELECT id FROM iam_policies WHERE username = ? AND policy_name = ?').get(p.username, p.name);
    if (!existing) {
      db.prepare('INSERT INTO iam_policies (username, policy_name, policy_json, created_by) VALUES (?, ?, ?, ?)').run(p.username, p.name, JSON.stringify(p.doc), p.by);
    }
  }

  // Resources
  const resources = [
    { arn: 'arn:aws:s3:::public-bucket',       label: 'Public Assets',            description: 'Marketing and public-facing static assets', data: 'marketing_assets_v2.zip', sensitivity: 'public',   owner: 'marketing', region: 'us-east-1' },
    { arn: 'arn:aws:s3:::sensitive-bucket',     label: 'Customer Records',         description: 'Encrypted PII and customer account data',   data: 'sample_token_redacted', sensitivity: 'private',  owner: 'data-team', region: 'us-east-1' },
    { arn: 'arn:aws:s3:::logs-bucket',          label: 'Audit Logs',               description: 'Centralized application and access logs',    data: 'audit_log_2024_01.gz', sensitivity: 'internal', owner: 'sre-team',  region: 'us-east-1' },
    { arn: 'arn:aws:s3:::reporting-bucket',     label: 'BI Reporting',             description: 'Business intelligence report exports',       data: 'bi_reports_q4_2023.parquet', sensitivity: 'internal', owner: 'bi-team',   region: 'us-west-2' },
    { arn: 'arn:aws:s3:::data-lake-bucket',     label: 'Data Lake Raw Zone',       description: 'Raw ingestion zone for the data lake',       data: 'raw_events_2024.json.gz', sensitivity: 'internal', owner: 'data-eng',  region: 'us-east-1' },
    { arn: 'arn:aws:s3:::ml-artifacts-bucket',  label: 'ML Model Artifacts',       description: 'Trained model checkpoints and metadata',     data: 'model_v3.4_checkpoint.pt', sensitivity: 'internal', owner: 'ml-team',   region: 'us-west-2' },
    { arn: 'arn:aws:s3:::backup-bucket',        label: 'Database Backups',         description: 'Nightly encrypted database backup snapshots', data: 'db_backup_20240115.tar.gz.enc', sensitivity: 'private',  owner: 'dba-team',  region: 'eu-west-1' },
    { arn: 'arn:aws:s3:::config-bucket',        label: 'Infrastructure Config',    description: 'Terraform state and infrastructure configs',  data: 'terraform.tfstate', sensitivity: 'private',  owner: 'platform',  region: 'us-east-1' },
    { arn: 'arn:aws:s3:::archive-bucket',       label: 'Cold Archive',             description: 'Regulatory compliance archive (7-year)',      data: 'archive_2017_2023.tar', sensitivity: 'internal', owner: 'compliance', region: 'us-east-1' },
    { arn: 'arn:aws:s3:::staging-bucket',       label: 'Staging Artifacts',        description: 'Pre-production build artifacts and assets',   data: 'release_candidate_v2.1.0.zip', sensitivity: 'internal', owner: 'devops',    region: 'us-east-1' },
  ];

  for (const r of resources) {
    try {
      db.prepare('INSERT OR IGNORE INTO resources (arn, label, description, data, sensitivity, owner, region) VALUES (?, ?, ?, ?, ?, ?, ?)').run(r.arn, r.label, r.description, r.data, r.sensitivity, r.owner, r.region);
    } catch (_) {}
  }

  // Tags
  const tags = [
    { arn: 'arn:aws:s3:::public-bucket',   key: 'env', value: 'production' },
    { arn: 'arn:aws:s3:::public-bucket',   key: 'team', value: 'marketing' },
    { arn: 'arn:aws:s3:::sensitive-bucket', key: 'env', value: 'production' },
    { arn: 'arn:aws:s3:::sensitive-bucket', key: 'classification', value: 'PII' },
    { arn: 'arn:aws:s3:::logs-bucket',     key: 'env', value: 'production' },
    { arn: 'arn:aws:s3:::logs-bucket',     key: 'retention', value: '90d' },
    { arn: 'arn:aws:s3:::data-lake-bucket', key: 'env', value: 'production' },
    { arn: 'arn:aws:s3:::data-lake-bucket', key: 'team', value: 'data-engineering' },
  ];

  for (const t of tags) {
    try {
      db.prepare('INSERT OR IGNORE INTO tags (resource_arn, tag_key, tag_value) VALUES (?, ?, ?)').run(t.arn, t.key, t.value);
    } catch (_) {}
  }

  // Sample audit log entries
  const sampleAuditEntries = [
    { actor: 'admin', action: 'auth:login', detail: 'Successful login', ip: '10.0.0.1' },
    { actor: 'dev1', action: 'auth:login', detail: 'Successful login', ip: '10.0.0.5' },
    { actor: 'analyst', action: 's3:GetObject', detail: 'arn:aws:s3:::public-bucket', ip: '10.0.0.8' },
    { actor: 'sre1', action: 's3:GetObject', detail: 'arn:aws:s3:::logs-bucket', ip: '10.0.0.12' },
    { actor: 'admin', action: 'iam:GeneratePolicyReport', detail: 'full org report', ip: '10.0.0.1' },
    { actor: 'dev2', action: 'auth:login', detail: 'Successful login', ip: '10.0.0.7' },
    { actor: 'secops1', action: 'iam:SimulatePrincipalPolicy', detail: 'user=dev1 action=s3:GetObject resource=arn:aws:s3:::sensitive-bucket result=false', ip: '10.0.0.20' },
    { actor: 'dataeng1', action: 's3:GetObject', detail: 'arn:aws:s3:::data-lake-bucket', ip: '10.0.0.15' },
  ];

  const existingAudit = db.prepare('SELECT COUNT(*) as cnt FROM audit_log').get().cnt;
  if (existingAudit === 0) {
    for (const e of sampleAuditEntries) {
      db.prepare('INSERT INTO audit_log (actor, action, detail, ip_address) VALUES (?, ?, ?, ?)').run(e.actor, e.action, e.detail, e.ip);
    }
  }

  // Sample notifications
  const existingNotif = db.prepare('SELECT COUNT(*) as cnt FROM notifications').get().cnt;
  if (existingNotif === 0) {
    db.prepare('INSERT INTO notifications (username, message) VALUES (?, ?)').run('dev1', 'Welcome to CloudLens! Your developer account has been provisioned.');
    db.prepare('INSERT INTO notifications (username, message) VALUES (?, ?)').run('analyst', 'Welcome to CloudLens! You have read access to the public bucket.');
    db.prepare('INSERT INTO notifications (username, message) VALUES (?, ?)').run('admin', 'System seeded with demo data. Review the policy report for a full overview.');
  }
}

seedDatabase();

// ─── Routes ──────────────────────────────────────────────────────────────────

const authRouter     = require('./routes/auth');
const dashboardRouter = require('./routes/dashboard');
const iamRouter      = require('./routes/iam');
const resourceRouter = require('./routes/resources');
const adminRouter    = require('./routes/admin');
const profileRouter  = require('./routes/profile');

app.use('/', authRouter);
app.use('/', requireLogin, dashboardRouter);
app.use('/iam', requireLogin, iamRouter);
app.use('/resources', requireLogin, resourceRouter);
app.use('/admin', requireLogin, adminRouter);
app.use('/profile', requireLogin, profileRouter);

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', {
    user: req.session && req.session.user,
    code: 404,
    message: 'The page you are looking for does not exist.',
    title: '404 — CloudLens'
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[CloudLens Error]', err.stack || err.message);
  res.status(500).render('error', {
    user: req.session && req.session.user,
    code: 500,
    message: 'An internal error occurred. Please try again later.',
    title: '500 — CloudLens'
  });
});

app.listen(9000, () => {
  console.log('[CloudLens] Platform running on http://localhost:9000');
  console.log('[CloudLens] Environment: ' + (process.env.NODE_ENV || 'development'));
});

module.exports = app;
