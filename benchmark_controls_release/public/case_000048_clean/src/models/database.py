import sqlite3
import bcrypt
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/flowci.db')


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'developer',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_name TEXT NOT NULL,
            token_value TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, token_name)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            repo_url TEXT,
            owner_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            build_count INTEGER DEFAULT 0,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS build_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            build_script TEXT,
            environment TEXT DEFAULT '{}',
            branch TEXT DEFAULT 'main',
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            config_id INTEGER,
            triggered_by INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            started_at TEXT,
            finished_at TEXT,
            log_output TEXT,
            commit_hash TEXT,
            branch TEXT DEFAULT 'main',
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (triggered_by) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL,
            details TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS server_properties (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()
    _seed_data(conn)
    conn.close()
    logger.info("Database initialized successfully")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _seed_data(conn):
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    users = [
        (1, 'admin', 'admin@flowci.local', _hash_password('AdminPass123!'), 'administrator', 1, now),
        (2, 'alice', 'alice@flowci.local', _hash_password('AlicePass123!'), 'developer', 1, now),
        (3, 'bob', 'bob@flowci.local', _hash_password('BobPass123!'), 'developer', 1, now),
        (4, 'charlie', 'charlie@flowci.local', _hash_password('CharliePass123!'), 'developer', 1, now),
        (5, 'diana', 'diana@flowci.local', _hash_password('DianaPass123!'), 'viewer', 1, now),
    ]
    for u in users:
        c.execute('''INSERT OR IGNORE INTO users (id, username, email, password_hash, role, is_active, created_at)
                     VALUES (?,?,?,?,?,?,?)''', u)

    projects = [
        (1, 'backend-api', 'Core REST API service', 'https://git.flowci.local/backend-api', 1, now, 47),
        (2, 'frontend-web', 'React web application', 'https://git.flowci.local/frontend-web', 2, now, 23),
        (3, 'mobile-app', 'iOS/Android mobile client', 'https://git.flowci.local/mobile-app', 2, now, 18),
        (4, 'data-pipeline', 'ETL and analytics pipeline', 'https://git.flowci.local/data-pipeline', 1, now, 31),
        (5, 'infra-tools', 'Infrastructure automation', 'https://git.flowci.local/infra-tools', 1, now, 12),
        (6, 'auth-service', 'Authentication microservice', 'https://git.flowci.local/auth-service', 3, now, 9),
        (7, 'notification-svc', 'Email/SMS notification service', 'https://git.flowci.local/notification-svc', 3, now, 5),
    ]
    for p in projects:
        c.execute('''INSERT OR IGNORE INTO projects (id, name, description, repo_url, owner_id, created_at, build_count)
                     VALUES (?,?,?,?,?,?,?)''', p)

    configs = [
        (1, 1, 'Build & Test', 'make test && make build', '{"GO_VERSION":"1.21"}', 'main'),
        (2, 1, 'Deploy Staging', 'make deploy-staging', '{"ENV":"staging"}', 'main'),
        (3, 2, 'npm build', 'npm ci && npm run build', '{"NODE_ENV":"production"}', 'main'),
        (4, 3, 'iOS Build', 'fastlane build_ios', '{"XCODE_VERSION":"15"}', 'main'),
        (5, 4, 'ETL Run', 'python etl/run.py', '{"SPARK_HOME":"/opt/spark"}', 'main'),
    ]
    for cfg in configs:
        c.execute('''INSERT OR IGNORE INTO build_configs (id, project_id, name, build_script, environment, branch)
                     VALUES (?,?,?,?,?,?)''', cfg)

    builds = [
        (1, 1, 1, 1, 'success', now, now, 'BUILD OK\nTests passed: 142/142', 'abc1234', 'main'),
        (2, 1, 1, 2, 'success', now, now, 'BUILD OK\nTests passed: 142/142', 'def5678', 'main'),
        (3, 2, 3, 2, 'failed', now, now, 'ERROR: Module not found', 'bbb2222', 'feature/login'),
        (4, 3, 4, 3, 'running', now, None, 'Compiling...', 'ccc3333', 'main'),
        (5, 4, 5, 1, 'success', now, now, 'Pipeline completed. 50000 rows processed.', 'ddd4444', 'main'),
        (6, 1, 2, 1, 'success', now, now, 'Deployed to staging.flowci.local', 'eee5555', 'main'),
        (7, 5, None, 1, 'queued', None, None, None, 'fff6666', 'main'),
        (8, 6, None, 3, 'success', now, now, 'Auth service deployed', 'ggg7777', 'main'),
        (9, 2, 3, 2, 'success', now, now, 'BUILD OK', 'hhh8888', 'main'),
        (10, 1, 1, 1, 'failed', now, now, 'Test failed: TestUserAuth', 'iii9999', 'feature/auth'),
    ]
    for b in builds:
        c.execute('''INSERT OR IGNORE INTO builds
                     (id, project_id, config_id, triggered_by, status, started_at, finished_at, log_output, commit_hash, branch)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''', b)

    audit_entries = [
        (1, 'user_login', 'user:1', '10.0.0.1', now, 'Successful login'),
        (2, 'build_triggered', 'build:1', '10.0.0.2', now, 'Triggered by webhook'),
        (1, 'project_created', 'project:1', '10.0.0.1', now, 'Created backend-api'),
        (2, 'build_triggered', 'build:3', '10.0.0.3', now, 'Manual trigger'),
        (3, 'token_created', 'token:ci-token', '10.0.0.4', now, 'CI token created'),
        (1, 'config_updated', 'config:1', '10.0.0.1', now, 'Updated build script'),
        (None, 'health_check', 'system', '10.0.0.100', now, 'Monitoring ping'),
        (1, 'user_login', 'user:2', '10.0.0.5', now, 'Successful login'),
        (2, 'project_updated', 'project:2', '10.0.0.2', now, 'Updated repo URL'),
        (1, 'deploy_triggered', 'build:6', '10.0.0.1', now, 'Deploy to staging'),
    ]
    for ae in audit_entries:
        c.execute('''INSERT OR IGNORE INTO audit_log (user_id, action, resource, ip_address, timestamp, details)
                     VALUES (?,?,?,?,?,?)''', ae)

    props = [
        ('server.version', '2023.05.3', now),
        ('server.name', 'FlowCI Build Server', now),
        ('build.history.limit', '100', now),
        ('rest.debug.processes.enable', 'false', now),
        ('notification.email.enabled', 'true', now),
        ('artifact.storage.path', '/app/data/artifacts', now),
    ]
    for prop in props:
        c.execute('''INSERT OR IGNORE INTO server_properties (key, value, updated_at)
                     VALUES (?,?,?)''', prop)

    conn.commit()
    logger.info("Seed data inserted")


def get_user_by_id(user_id: int):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_token(token_value: str):
    conn = get_db()
    try:
        row = conn.execute(
            '''SELECT u.* FROM api_tokens t
               JOIN users u ON t.user_id = u.id
               WHERE t.token_value = ? AND u.is_active = 1''',
            (token_value,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def write_audit(user_id, action, resource, ip_address, details=''):
    conn = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO audit_log (user_id, action, resource, ip_address, timestamp, details) VALUES (?,?,?,?,?,?)',
            (user_id, action, resource, ip_address, now, details)
        )
        conn.commit()
    finally:
        conn.close()