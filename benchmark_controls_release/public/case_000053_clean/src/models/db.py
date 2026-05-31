import sqlite3
import os
import logging
import bcrypt

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    is_verified INTEGER NOT NULL DEFAULT 0,
    verification_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    project_id INTEGER NOT NULL,
    assigned_to INTEGER,
    created_by INTEGER NOT NULL,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    user_agent TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    ip_address TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def get_db(db_path=None):
    if db_path is None:
        db_path = os.environ.get('DATABASE_PATH', 'taskflow.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    logger.info(f'Initializing database at {db_path}')
    conn = get_db(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _seed_data(conn)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error(f'Error initializing database: {e}')
        raise
    finally:
        conn.close()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _seed_data(conn):
    # Check if already seeded
    existing = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    if existing['c'] > 0:
        return

    logger.info('Seeding initial data...')

    # Seed users
    users = [
        ('alice', 'alice@taskflow.io', _hash_password('AlicePass123!'), 'admin', 1),
        ('bob', 'bob@taskflow.io', _hash_password('BobPass123!'), 'member', 1),
        ('charlie', 'charlie@taskflow.io', _hash_password('CharliePass123!'), 'member', 1),
        ('diana', 'diana@taskflow.io', _hash_password('DianaPass456!'), 'member', 1),
        ('eve', 'eve@taskflow.io', _hash_password('EvePass789!'), 'member', 1),
        ('frank', 'frank@taskflow.io', _hash_password('FrankPass321!'), 'member', 1),
        ('grace', 'grace@taskflow.io', _hash_password('GracePass654!'), 'member', 1),
    ]

    for username, email, pw_hash, role, verified in users:
        try:
            conn.execute(
                "INSERT INTO users (username, email, password_hash, role, is_verified) VALUES (?, ?, ?, ?, ?)",
                (username, email, pw_hash, role, verified)
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()

    # Seed projects
    projects = [
        ('Platform Rewrite', 'Complete overhaul of the core platform', 1, 'active'),
        ('Mobile App v2', 'New mobile application for iOS and Android', 1, 'active'),
        ('API Gateway', 'Centralized API gateway implementation', 2, 'active'),
        ('Analytics Dashboard', 'Real-time analytics and reporting', 2, 'active'),
        ('DevOps Pipeline', 'CI/CD pipeline improvements', 3, 'active'),
        ('Customer Portal', 'Self-service customer portal', 3, 'archived'),
    ]

    for name, desc, owner_id, status in projects:
        try:
            conn.execute(
                "INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)",
                (name, desc, owner_id, status)
            )
        except Exception:
            pass

    conn.commit()

    # Seed tasks
    tasks = [
        ('Set up CI pipeline', 'Configure GitHub Actions for automated testing', 1, 1, 1, 'in_progress', 'high', '2025-07-01'),
        ('Design new DB schema', 'Redesign tables for better performance', 1, 2, 1, 'todo', 'high', '2025-06-30'),
        ('Write API docs', 'Document all REST endpoints with OpenAPI', 2, 2, 1, 'todo', 'medium', '2025-07-15'),
        ('Implement OAuth2', 'Add OAuth2 provider support', 1, 3, 1, 'in_progress', 'high', '2025-07-10'),
        ('Fix login page CSS', 'Responsive design fixes for mobile', 2, 4, 2, 'done', 'low', '2025-06-15'),
        ('Performance profiling', 'Profile and optimize slow queries', 3, 1, 2, 'todo', 'medium', '2025-07-20'),
        ('Add dark mode', 'Implement dark mode theme support', 2, 5, 2, 'todo', 'low', '2025-08-01'),
        ('Rate limiting middleware', 'Add rate limiting to all public endpoints', 1, 3, 3, 'in_progress', 'high', '2025-06-25'),
        ('Email notification system', 'Set up transactional email via SendGrid', 4, 2, 3, 'todo', 'medium', '2025-07-05'),
        ('User onboarding flow', 'Create guided onboarding for new users', 4, 4, 3, 'todo', 'medium', '2025-07-18'),
        ('Billing integration', 'Stripe payment integration', 4, 1, 1, 'todo', 'high', '2025-07-30'),
        ('SAML SSO support', 'Enterprise SSO via SAML 2.0', 1, 2, 1, 'todo', 'high', '2025-08-15'),
        ('Audit log viewer', 'Admin view for audit trail', 5, 1, 2, 'in_progress', 'medium', '2025-07-12'),
        ('Webhook delivery retry', 'Implement exponential backoff for webhooks', 3, 3, 2, 'todo', 'medium', '2025-07-22'),
        ('Load test suite', 'k6 load testing scripts for API endpoints', 5, 1, 3, 'todo', 'high', '2025-07-08'),
    ]

    for title, desc, project_id, assigned_to, created_by, status, priority, due_date in tasks:
        try:
            conn.execute(
                """INSERT INTO tasks (title, description, project_id, assigned_to, created_by, status, priority, due_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, desc, project_id, assigned_to, created_by, status, priority, due_date)
            )
        except Exception:
            pass

    conn.commit()
    logger.info('Seed data inserted successfully')