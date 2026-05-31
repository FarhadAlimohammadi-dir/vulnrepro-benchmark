'use strict';

const db = require('./db');

function seedDatabase() {
  // Seed users
  const users = [
    {
      username: 'admin',
      password: 'admin123',
      email: 'admin@corp.example.com',
      full_name: 'Alexandra Chen',
      role: 'admin',
      department: 'Platform Engineering'
    },
    {
      username: 'dev',
      password: 'dev456',
      email: 'dev@corp.example.com',
      full_name: 'Marcus Webb',
      role: 'developer',
      department: 'Software Engineering'
    },
    {
      username: 'auditor',
      password: 'audit789',
      email: 'auditor@corp.example.com',
      full_name: 'Sandra Kim',
      role: 'auditor',
      department: 'Security & Compliance'
    },
    {
      username: 'devops_lead',
      password: 'devops2024!',
      email: 'devops@corp.example.com',
      full_name: 'James Harrington',
      role: 'developer',
      department: 'DevOps'
    },
    {
      username: 'sre_team',
      password: 'sre#secure1',
      email: 'sre@corp.example.com',
      full_name: 'SRE Team Account',
      role: 'developer',
      department: 'Site Reliability'
    }
  ];

  const insertUser = db.prepare(`
    INSERT OR IGNORE INTO users (username, password, email, full_name, role, department)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  users.forEach(u => {
    insertUser.run(u.username, u.password, u.email, u.full_name, u.role, u.department);
  });

  // Seed OIDC providers
  const providers = [
    {
      name: 'GitHub Actions',
      issuer_url: 'https://token.actions.githubusercontent.com',
      thumbprint: '6938fd4d98bab03faadb97b34396831e3780aea1',
      audiences: JSON.stringify(['sts.amazonaws.com'])
    },
    {
      name: 'Terraform Cloud',
      issuer_url: 'https://app.terraform.io',
      thumbprint: '9e99a48a9960b14926bb7f3b02e22da2b0ab7280',
      audiences: JSON.stringify(['aws.terraform.io'])
    },
    {
      name: 'GitLab CI',
      issuer_url: 'https://gitlab.com',
      thumbprint: 'b3dd7606d2b5a8b4a13771dbecc9ee1cecafa38a',
      audiences: JSON.stringify(['https://gitlab.com'])
    },
    {
      name: 'CircleCI',
      issuer_url: 'https://oidc.circleci.com/org/abc123',
      thumbprint: 'aa3729a3f77d0f1beebb9c5bcd5b3c7a87a8f3c0',
      audiences: JSON.stringify(['sts.amazonaws.com'])
    }
  ];

  const insertProvider = db.prepare(`
    INSERT OR IGNORE INTO providers (name, issuer_url, thumbprint, audiences)
    VALUES (?, ?, ?, ?)
  `);

  providers.forEach(p => {
    insertProvider.run(p.name, p.issuer_url, p.thumbprint, p.audiences);
  });

  // Seed trust policies
  const adminUser = db.prepare('SELECT id FROM users WHERE username = ?').get('admin');
  const devUser = db.prepare('SELECT id FROM users WHERE username = ?').get('dev');
  const devopsUser = db.prepare('SELECT id FROM users WHERE username = ?').get('devops_lead');

  const policies = [
    {
      name: 'github-actions-prod-missing-conditions',
      description: 'Production deployment role for main branch CI/CD pipeline (under review)',
      provider: 'github-actions',
      environment: 'production',
      role_arn: 'arn:aws:iam::123456789012:role/github-actions-prod',
      owner_id: devopsUser ? devopsUser.id : 1,
      tags: JSON.stringify(['production', 'ci-cd', 'github']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          }
        }
      })
    },
    {
      name: 'github-actions-staging-full-conditions',
      description: 'Staging deployment role with complete condition set for release branches',
      provider: 'github-actions',
      environment: 'staging',
      role_arn: 'arn:aws:iam::123456789012:role/github-actions-staging',
      owner_id: devopsUser ? devopsUser.id : 1,
      tags: JSON.stringify(['staging', 'ci-cd', 'github']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:CorpOrg/platform-services:ref:refs/heads/release"
          }
        }
      })
    },
    {
      name: 'terraform-cloud-infra-provisioner',
      description: 'Terraform Cloud workspace access for infrastructure provisioning',
      provider: 'terraform-cloud',
      environment: 'production',
      role_arn: 'arn:aws:iam::123456789012:role/terraform-infra-provisioner',
      owner_id: adminUser ? adminUser.id : 1,
      tags: JSON.stringify(['terraform', 'infra', 'production']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/app.terraform.io"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "app.terraform.io:aud": "aws.terraform.io",
            "app.terraform.io:sub": "organization:CorpOrg:project:infrastructure:workspace:prod:run_phase:apply"
          }
        }
      })
    },
    {
      name: 'gitlab-ci-container-registry',
      description: 'GitLab CI pipeline access to ECR for container image publishing',
      provider: 'gitlab',
      environment: 'production',
      role_arn: 'arn:aws:iam::123456789012:role/gitlab-ecr-publisher',
      owner_id: devUser ? devUser.id : 2,
      tags: JSON.stringify(['gitlab', 'containers', 'ecr']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "gitlab.com:aud": "https://gitlab.com",
            "gitlab.com:sub": "project_path:corp-group/container-builds:ref_type:branch:ref:main"
          }
        }
      })
    },
    {
      name: 'github-actions-dev-readonly',
      description: 'Read-only access for development branch CI checks and test runners',
      provider: 'github-actions',
      environment: 'development',
      role_arn: 'arn:aws:iam::123456789012:role/github-actions-dev-ro',
      owner_id: devUser ? devUser.id : 2,
      tags: JSON.stringify(['development', 'readonly', 'github']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:CorpOrg/platform-services:ref:refs/heads/develop"
          }
        }
      })
    },
    {
      name: 'circleci-integration-tests',
      description: 'CircleCI organization context for running integration test suite',
      provider: 'circleci',
      environment: 'staging',
      role_arn: 'arn:aws:iam::123456789012:role/circleci-integration-runner',
      owner_id: adminUser ? adminUser.id : 1,
      tags: JSON.stringify(['circleci', 'testing', 'staging']),
      trust_policy: JSON.stringify({
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.circleci.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "oidc.circleci.com:aud": "sts.amazonaws.com",
            "oidc.circleci.com:sub": "org/abc123-def456/project/platform-services/user/xyz789"
          }
        }
      })
    }
  ];

  const insertPolicy = db.prepare(`
    INSERT OR IGNORE INTO policies (name, description, provider, environment, role_arn, owner_id, tags, trust_policy)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  policies.forEach(p => {
    insertPolicy.run(p.name, p.description, p.provider, p.environment, p.role_arn, p.owner_id, p.tags, p.trust_policy);
  });

  // Seed some audit log entries
  const auditEntries = [
    { username: 'admin', action: 'POLICY_CREATED', resource_type: 'policy', resource_id: '1', details: 'Created github-actions-prod policy', status: 'success' },
    { username: 'devops_lead', action: 'POLICY_UPDATED', resource_type: 'policy', resource_id: '1', details: 'Updated trust conditions', status: 'success' },
    { username: 'dev', action: 'ROLE_ASSUMED', resource_type: 'policy', resource_id: '2', details: 'Staging role assumption for deployment', status: 'success' },
    { username: 'auditor', action: 'POLICY_VIEWED', resource_type: 'policy', resource_id: '1', details: 'Compliance review', status: 'success' },
    { username: 'admin', action: 'USER_LOGIN', resource_type: 'user', resource_id: '1', details: 'Admin login from corporate network', status: 'success' },
    { username: 'sre_team', action: 'POLICY_EVALUATED', resource_type: 'policy', resource_id: '3', details: 'Terraform workspace evaluation', status: 'success' }
  ];

  const insertAudit = db.prepare(`
    INSERT OR IGNORE INTO audit_log (username, action, resource_type, resource_id, details, status)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  auditEntries.forEach(e => {
    try {
      insertAudit.run(e.username, e.action, e.resource_type, e.resource_id, e.details, e.status);
    } catch (_) {}
  });

  // Seed notifications
  const insertNotif = db.prepare(`
    INSERT OR IGNORE INTO notifications (user_id, title, body)
    VALUES (?, ?, ?)
  `);

  const devRow = db.prepare('SELECT id FROM users WHERE username = ?').get('dev');
  if (devRow) {
    try {
      insertNotif.run(devRow.id, 'Policy Review Required', 'The github-actions-prod policy is scheduled for quarterly review.');
      insertNotif.run(devRow.id, 'New Provider Added', 'CircleCI OIDC provider has been registered in your account.');
    } catch (_) {}
  }

  console.log('[INFO] Database seeded successfully');
}

module.exports = { seedDatabase };