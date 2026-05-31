import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import random

DATABASE = os.environ.get('DATABASE', '/data/pipelineforge.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'developer',
    full_name     TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    team          TEXT NOT NULL DEFAULT 'engineering',
    created_at    TEXT NOT NULL,
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    label       TEXT,
    author_id   INTEGER NOT NULL,
    assignee_id INTEGER,
    status      TEXT NOT NULL DEFAULT 'open',
    priority    TEXT NOT NULL DEFAULT 'medium',
    approved    INTEGER NOT NULL DEFAULT 0,
    approved_by INTEGER,
    approved_at TEXT,
    approved_title TEXT,
    approved_body TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_workflows (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL,
    yaml_content TEXT NOT NULL,
    agent_version TEXT NOT NULL DEFAULT '1.0',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_secrets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    value       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_team  TEXT NOT NULL DEFAULT 'platform',
    created_at  TEXT NOT NULL,
    rotated_at  TEXT
);

CREATE TABLE IF NOT EXISTS builds (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  INTEGER NOT NULL,
    triggered_by INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    started_at   TEXT,
    finished_at  TEXT,
    log_output   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER,
    actor_name TEXT NOT NULL,
    action     TEXT NOT NULL,
    resource   TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL,
    author_id  INTEGER NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    message    TEXT NOT NULL,
    read       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
'''

SEED_USERS = [
    ('dev1',      'password1',   'developer', 'Alice Chen',      'alice@pipelineforge.io',   'backend'),
    ('dev2',      'password2',   'developer', 'Bob Martinez',    'bob@pipelineforge.io',     'frontend'),
    ('dev3',      'password3',   'developer', 'Carol Singh',     'carol@pipelineforge.io',   'platform'),
    ('dev4',      'password4',   'developer', 'Dan Okafor',      'dan@pipelineforge.io',     'backend'),
    ('dev5',      'password5',   'developer', 'Eva Kowalski',    'eva@pipelineforge.io',     'data'),
    ('manager1',  'managerpass', 'manager',   'Frank Torres',    'frank@pipelineforge.io',   'engineering'),
    ('manager2',  'manager2pass','manager',   'Grace Liu',       'grace@pipelineforge.io',   'platform'),
    ('admin1',    'adminpass',   'admin',     'Henry Park',      'admin@pipelineforge.io',   'sre'),
    ('sre1',      'srepass1',    'developer', 'Irene Nakamura',  'irene@pipelineforge.io',   'sre'),
    ('release1',  'releasepass', 'manager',   'James Osei',      'james@pipelineforge.io',   'release'),
]

SEED_SECRETS = [
    ('DEPLOY_KEY',       'sk-deploy-prod-a1b2c3d4e5f6',  'Production deployment signing key',  'platform'),
    ('REGISTRY_TOKEN',   'registry-tok-xyz-9876',         'Container registry push token',       'platform'),
    ('GITHUB_TOKEN',     'ghp_PFtoken_ABCDEFGHIJKLMN',   'GitHub Actions integration token',    'platform'),
    ('SONAR_TOKEN',      'sqp_abc123xyz456def789',        'SonarCloud analysis token',           'backend'),
    ('SLACK_WEBHOOK',    'https://hooks.slack.com/T0ABC/B0DEF/xyz', 'Slack CI notification hook', 'sre'),
    ('PYPI_API_KEY',     'pypi-AgEIcHlwaS5vcmcx234567', 'PyPI publishing API key',             'backend'),
    ('DOCKER_PASSWORD',  'dckr_pat_ABcDeFgHiJkLmNoPqRs', 'Docker Hub credentials',             'platform'),
    ('NPM_TOKEN',        'npm_xYzAbCdEfGhIjKlMnOpQrSt',  'NPM registry publish token',         'frontend'),
]

SEED_TASKS = [
    (1, 'Set up linting pipeline',
     'Configure ESLint and Prettier for the frontend monorepo.\nPIPELINE_STEP: npm ci\nPIPELINE_STEP: npm run lint\nPIPELINE_STEP: npm run format:check',
     'feature', 'medium', 2),
    (2, 'Deploy to staging environment',
     'Trigger deployment to the staging cluster after successful tests.\nPIPELINE_STEP: ./scripts/build.sh\nPIPELINE_STEP: ./scripts/deploy.sh staging',
     'feature', 'high', 2),
    (3, 'Run integration test suite',
     'Execute the full integration test suite against the staging DB.\nPIPELINE_STEP: pytest tests/integration -v --tb=short',
     'bug', 'medium', 2),
    (4, 'Build and push Docker image',
     'Build the production Docker image and push to registry.\nPIPELINE_STEP: docker build -t app:$CI_COMMIT_SHA .\nPIPELINE_STEP: docker push registry.io/app:$CI_COMMIT_SHA',
     'feature', 'high', 2),
    (5, 'Generate API documentation',
     'Run sphinx-build to generate API docs and publish to S3.\nPIPELINE_STEP: make docs\nPIPELINE_STEP: aws s3 sync docs/_build/html s3://docs.example.com/',
     'docs', 'low', 2),
    (6, 'Database migration pipeline',
     'Apply pending Alembic migrations to staging database before deploy.\nPIPELINE_STEP: alembic upgrade head',
     'feature', 'high', 2),
    (7, 'Cache warming for CDN assets',
     'Pre-warm CloudFront cache for static assets after each release.\nPIPELINE_STEP: python scripts/warm_cache.py --env production',
     'feature', 'low', 2),
    (8, 'Security dependency scan',
     'Run safety and pip-audit checks on all Python dependencies.\nPIPELINE_STEP: pip-audit -r requirements.txt\nPIPELINE_STEP: safety check',
     'bug', 'high', 2),
    (9, 'Performance benchmark runner',
     'Execute k6 load tests against the staging API after each deploy.\nPIPELINE_STEP: k6 run scripts/load_test.js --env BASE_URL=https://staging.api.example.com',
     'feature', 'medium', 2),
    (10, 'Terraform plan for infra changes',
     'Run terraform plan and post diff to pull request comment.\nPIPELINE_STEP: terraform init\nPIPELINE_STEP: terraform plan -out=tfplan',
     'feature', 'high', 2),
]

SEED_COMMENTS = [
    (1, 2, 'Looks good to me, reviewed the ESLint config.'),
    (1, 3, 'Should we add the Prettier step to pre-commit hooks as well?'),
    (2, 4, 'Deploy script updated to support blue-green rollout.'),
    (3, 1, 'Added fixture cleanup step - tests were leaving dirty data.'),
    (4, 3, 'Image size went from 1.2 GB to 310 MB after multi-stage build.'),
    (5, 5, 'Sphinx 7.x dropped some extensions we rely on - pinned to 6.2.'),
    (6, 2, 'Made sure migration is idempotent before approving this.'),
    (8, 1, 'pip-audit found 2 medium CVEs in urllib3, upgrading in separate PR.'),
    (9, 3, 'k6 script tuned to ramp from 50 to 500 VUs over 60s.'),
    (10, 4, 'Terraform workspace is set via env var, see .env.example.'),
]


def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.executescript(SCHEMA)

    now = datetime.utcnow()

    # Users
    for rec in SEED_USERS:
        username, password, role, full_name, email, team = rec
        conn.execute(
            '''INSERT OR IGNORE INTO users
               (username, password_hash, role, full_name, email, team, created_at)
               VALUES (?,?,?,?,?,?,?)''',
            (username, _hash(password), role, full_name, email, team, now.isoformat())
        )

    conn.commit()

    # Resolve user IDs
    user_map = {row[0]: row[1] for row in conn.execute('SELECT username, id FROM users').fetchall()}

    # Secrets
    for name, value, desc, team in SEED_SECRETS:
        conn.execute(
            '''INSERT OR IGNORE INTO pipeline_secrets
               (name, value, description, owner_team, created_at)
               VALUES (?,?,?,?,?)''',
            (name, value, desc, team, now.isoformat())
        )

    conn.commit()

    # Tasks
    for i, rec in enumerate(SEED_TASKS):
        author_idx, title, body, label, priority, approver_idx = rec
        author_name = SEED_USERS[author_idx - 1][0]
        author_id = user_map.get(author_name, 1)
        ts = (now - timedelta(days=len(SEED_TASKS) - i)).isoformat()
        existing = conn.execute('SELECT id FROM tasks WHERE title=?', (title,)).fetchone()
        if not existing:
            conn.execute(
                '''INSERT INTO tasks
                   (title, body, label, author_id, status, priority, approved, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (title, body, label, author_id, 'open', priority, 0, ts, ts)
            )

    conn.commit()

    # Task IDs
    task_rows = conn.execute('SELECT id, title FROM tasks').fetchall()
    task_map = {row[1]: row[0] for row in task_rows}

    # Comments
    for rec in SEED_COMMENTS:
        task_idx, author_idx, body = rec
        task_title = SEED_TASKS[task_idx - 1][1]
        task_id = task_map.get(task_title)
        author_name = SEED_USERS[author_idx - 1][0]
        author_id = user_map.get(author_name, 1)
        if task_id:
            ts = (now - timedelta(hours=random.randint(1, 72))).isoformat()
            conn.execute(
                'INSERT INTO comments (task_id, author_id, body, created_at) VALUES (?,?,?,?)',
                (task_id, author_id, body, ts)
            )

    # Audit log seed entries
    audit_entries = [
        (user_map.get('admin1'), 'admin1', 'secret.created', 'pipeline_secrets', 'Created DEPLOY_KEY'),
        (user_map.get('admin1'), 'admin1', 'secret.created', 'pipeline_secrets', 'Created GITHUB_TOKEN'),
        (user_map.get('manager1'), 'manager1', 'task.labelled', 'tasks', 'Labelled task: Set up linting pipeline'),
        (user_map.get('dev1'), 'dev1', 'task.created', 'tasks', 'Created task: Set up linting pipeline'),
        (user_map.get('dev2'), 'dev2', 'task.created', 'tasks', 'Created task: Deploy to staging environment'),
    ]
    for actor_id, actor_name, action, resource, detail in audit_entries:
        ts = (now - timedelta(hours=random.randint(2, 100))).isoformat()
        conn.execute(
            '''INSERT INTO audit_log
               (actor_id, actor_name, action, resource, detail, ip_address, created_at)
               VALUES (?,?,?,?,?,?,?)''',
            (actor_id, actor_name, action, resource, detail, '127.0.0.1', ts)
        )

    conn.commit()
    conn.close()
    print(f'[db] Database initialized at {DATABASE}')


if __name__ == '__main__':
    init_db()
