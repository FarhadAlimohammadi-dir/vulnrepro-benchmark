'use strict';

const { getDB } = require('./models/database');
const { hashPassword } = require('./models/userModel');

const DEPARTMENTS = [
  { name: 'Engineering', manager: 'Carol Whitfield', headcount: 42 },
  { name: 'Human Resources', manager: 'Dan Kowalski', headcount: 15 },
  { name: 'Finance', manager: 'Priya Ramesh', headcount: 20 },
  { name: 'Operations', manager: 'James Thorn', headcount: 35 },
  { name: 'Legal', manager: 'Sandra Vu', headcount: 8 },
  { name: 'Marketing', manager: 'Leo Barnes', headcount: 18 },
  { name: 'General', manager: '', headcount: 0 }
];

const SYSTEMS = [
  { name: 'Workday HCM', description: 'HR management platform', owner: 'HR', classification: 'CONFIDENTIAL' },
  { name: 'Jira Service Desk', description: 'IT help desk ticketing', owner: 'IT', classification: 'INTERNAL' },
  { name: 'Salesforce CRM', description: 'Customer relationship management', owner: 'Sales', classification: 'CONFIDENTIAL' },
  { name: 'AWS Production', description: 'Cloud infrastructure access', owner: 'Engineering', classification: 'RESTRICTED' },
  { name: 'GitHub Enterprise', description: 'Source code repository', owner: 'Engineering', classification: 'CONFIDENTIAL' },
  { name: 'Tableau Analytics', description: 'Business intelligence dashboards', owner: 'Finance', classification: 'INTERNAL' },
  { name: 'Confluence Wiki', description: 'Internal documentation', owner: 'IT', classification: 'INTERNAL' },
  { name: 'SAP ERP', description: 'Enterprise resource planning', owner: 'Finance', classification: 'RESTRICTED' }
];

const SEED_USERS = [
  { username: 'alice@target.com', password: 'pass123', employee_name: 'Alice Smith', department: 'Engineering', title: 'Senior Engineer', roles: 'IC_REQUESTER' },
  { username: 'bob@target.com', password: 'pass123', employee_name: 'Bob Jones', department: 'Engineering', title: 'DevOps Engineer', roles: 'IC_REQUESTER' },
  { username: 'carol@target.com', password: 'pass123', employee_name: 'Carol Whitfield', department: 'Engineering', title: 'Engineering Manager', roles: 'REQUESTER' },
  { username: 'dan@target.com', password: 'pass123', employee_name: 'Dan Kowalski', department: 'Human Resources', title: 'HR Director', roles: 'REQUESTER' },
  { username: 'priya@target.com', password: 'pass123', employee_name: 'Priya Ramesh', department: 'Finance', title: 'Finance Manager', roles: 'REQUESTER' },
  { username: 'james@target.com', password: 'pass123', employee_name: 'James Thorn', department: 'Operations', title: 'Operations Lead', roles: 'IC_REQUESTER' },
  { username: 'sandra@target.com', password: 'pass123', employee_name: 'Sandra Vu', department: 'Legal', title: 'General Counsel', roles: 'VIEWER' },
  { username: 'leo@target.com', password: 'pass123', employee_name: 'Leo Barnes', department: 'Marketing', title: 'Marketing Manager', roles: 'IC_REQUESTER' },
  { username: 'mia@target.com', password: 'pass123', employee_name: 'Mia Chen', department: 'Engineering', title: 'Software Engineer', roles: 'IC_REQUESTER' },
  { username: 'omar@target.com', password: 'pass123', employee_name: 'Omar Farouk', department: 'Operations', title: 'Systems Analyst', roles: 'IC_REQUESTER' },
  { username: 'lisa@target.com', password: 'pass123', employee_name: 'Lisa Park', department: 'Human Resources', title: 'HR Generalist', roles: 'IC_REQUESTER' },
  { username: 'admin@target.com', password: 'admin123', employee_name: 'Admin User', department: 'IT', title: 'System Administrator', roles: 'ADMIN' },
  { username: 'sysadmin@target.com', password: 'admin456', employee_name: 'Sys Admin', department: 'IT', title: 'Platform Engineer', roles: 'ADMIN AND REQUESTER' }
];

const SEED_REQUESTS = [
  { username: 'alice@target.com', title: 'GitHub Enterprise access for new repo', system_name: 'GitHub Enterprise', access_level: 'WRITE', status: 'APPROVED', description: 'Need write access to deploy new microservice repo.' },
  { username: 'bob@target.com', title: 'AWS Production read access for diagnostics', system_name: 'AWS Production', access_level: 'READ', status: 'PENDING', description: 'Requires read-only access to CloudWatch logs for incident review.' },
  { username: 'carol@target.com', title: 'Workday manager approval permissions', system_name: 'Workday HCM', access_level: 'WRITE', status: 'APPROVED', description: 'Manager-level access for headcount approvals.' },
  { username: 'dan@target.com', title: 'Workday full admin access', system_name: 'Workday HCM', access_level: 'ADMIN', status: 'PENDING', description: 'Full admin for HR workflow configuration.' },
  { username: 'priya@target.com', title: 'SAP ERP reporting access', system_name: 'SAP ERP', access_level: 'READ', status: 'APPROVED', description: 'Finance team read access for month-end reports.' },
  { username: 'james@target.com', title: 'Jira Service Desk agent role', system_name: 'Jira Service Desk', access_level: 'WRITE', status: 'PENDING', description: 'Need agent access to manage IT tickets for Operations.' },
  { username: 'leo@target.com', title: 'Salesforce CRM view access', system_name: 'Salesforce CRM', access_level: 'READ', status: 'REJECTED', description: 'Marketing campaign analysis requires CRM view.' },
  { username: 'mia@target.com', title: 'Tableau dashboard access', system_name: 'Tableau Analytics', access_level: 'READ', status: 'APPROVED', description: 'Need access to engineering KPI dashboards.' },
  { username: 'omar@target.com', title: 'Confluence engineering space', system_name: 'Confluence Wiki', access_level: 'WRITE', status: 'PENDING', description: 'Documenting infrastructure runbooks.' },
  { username: 'lisa@target.com', title: 'Workday HR reporting view', system_name: 'Workday HCM', access_level: 'READ', status: 'APPROVED', description: 'Read access for monthly headcount reporting.' },
  { username: 'alice@target.com', title: 'AWS staging environment access', system_name: 'AWS Production', access_level: 'WRITE', status: 'PENDING', description: 'Staging deploy access for Q3 release cycle.' },
  { username: 'bob@target.com', title: 'GitHub Enterprise admin for org settings', system_name: 'GitHub Enterprise', access_level: 'ADMIN', status: 'REJECTED', description: 'Admin access to manage org-level security settings.' }
];

function seedDatabase() {
  const db = getDB();

  // Seed departments
  const deptStmt = db.prepare('INSERT OR IGNORE INTO departments (name, manager, headcount) VALUES (?, ?, ?)');
  for (const d of DEPARTMENTS) {
    deptStmt.run(d.name, d.manager, d.headcount);
  }

  // Seed system catalog
  const sysStmt = db.prepare('INSERT OR IGNORE INTO system_catalog (name, description, owner, classification) VALUES (?, ?, ?, ?)');
  for (const s of SYSTEMS) {
    sysStmt.run(s.name, s.description, s.owner, s.classification);
  }

  // Seed users
  const userStmt = db.prepare(
    'INSERT OR IGNORE INTO users (username, password, employee_name, department, title, enabled, roles) VALUES (?, ?, ?, ?, ?, 1, ?)'
  );
  for (const u of SEED_USERS) {
    userStmt.run(u.username, hashPassword(u.password), u.employee_name, u.department, u.title, u.roles);
  }

  // Seed access requests
  const reqStmt = db.prepare(
    'INSERT OR IGNORE INTO access_requests (user_id, title, description, system_name, access_level, status) VALUES (?, ?, ?, ?, ?, ?)'
  );
  for (const r of SEED_REQUESTS) {
    const user = db.prepare('SELECT id FROM users WHERE username = ?').get(r.username);
    if (user) {
      // Only insert if user has no requests yet to keep seed idempotent
      const existing = db.prepare('SELECT id FROM access_requests WHERE user_id = ? AND title = ?').get(user.id, r.title);
      if (!existing) {
        reqStmt.run(user.id, r.title, r.description, r.system_name, r.access_level, r.status);
      }
    }
  }

  console.log('[INFO] Database seeded successfully');
}

module.exports = { seedDatabase };