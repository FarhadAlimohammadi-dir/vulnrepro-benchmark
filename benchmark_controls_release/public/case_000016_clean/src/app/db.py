import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get('DB_PATH', '/data/devflow.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'developer'
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    repo_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    task_name TEXT,
    command TEXT,
    user_id INTEGER,
    status TEXT DEFAULT 'pending',
    output TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''

DEMO_USERS = [
    ('alice',    'developer'),
    ('bob',      'developer'),
    ('carol',    'developer'),
    ('dave',     'viewer'),
    ('eve',      'viewer'),
    ('frank',    'developer'),
    ('grace',    'developer'),
    ('heidi',    'viewer'),
    ('ivan',     'developer'),
    ('judy',     'developer'),
]

SEED_PROJECTS = [
    ('backend-api',      'Main REST API service',            '/workspace/backend-api'),
    ('frontend-app',     'React frontend',                   '/workspace/frontend-app'),
    ('ml-pipeline',      'Data pipeline scripts',            '/workspace/ml-pipeline'),
    ('infra-terraform',  'Infrastructure as code',           '/workspace/infra-terraform'),
    ('docs-site',        'Static documentation site',        '/workspace/docs-site'),
    ('mobile-ios',       'iOS client application',           '/workspace/mobile-ios'),
    ('mobile-android',   'Android client application',       '/workspace/mobile-android'),
    ('data-warehouse',   'ETL jobs and dbt models',          '/workspace/data-warehouse'),
    ('auth-service',     'Identity and token management',    '/workspace/auth-service'),
    ('notification-svc', 'Email / push notification worker', '/workspace/notification-svc'),
]

SEED_AUDIT = [
    (1, 'user.login',          'admin logged in from 10.0.0.1'),
    (2, 'task.run',            'alice ran pytest on backend-api'),
    (3, 'task.run',            'bob ran go test on auth-service'),
    (1, 'project.created',     'admin created infra-terraform'),
    (2, 'user.password_change','alice changed her password'),
    (4, 'task.run',            'carol ran rg on ml-pipeline'),
    (1, 'role.updated',        'admin promoted frank to developer'),
]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    seed_users = []
    admin_password = os.environ.get('INITIAL_ADMIN_PASSWORD')
    if admin_password:
        seed_users.insert(0, ('admin', admin_password, 'admin'))
    if os.environ.get('SEED_DEMO_USERS') == '1':
        for username, role in DEMO_USERS:
            user_password = os.environ.get(f'DEMO_PASSWORD_{username.upper()}')
            if user_password:
                seed_users.append((username, user_password, role))

    for username, password, role in seed_users:
        try:
            con.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                (username, generate_password_hash(password), role)
            )
        except sqlite3.IntegrityError:
            pass

    for name, desc, path in SEED_PROJECTS:
        try:
            con.execute(
                'INSERT INTO projects (name, description, repo_path) VALUES (?,?,?)',
                (name, desc, path)
            )
        except sqlite3.IntegrityError:
            pass

    for user_id, action, detail in SEED_AUDIT:
        try:
            con.execute(
                'INSERT INTO audit_log (user_id, action, detail) VALUES (?,?,?)',
                (user_id, action, detail)
            )
        except Exception:
            pass

    con.commit()
    con.close()
    print(f'[db] Initialized at {DB_PATH}')


if __name__ == '__main__':
    init_db()
