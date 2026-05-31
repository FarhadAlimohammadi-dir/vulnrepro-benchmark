import sqlite3
import os
import logging
import secrets
import bcrypt

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'projectflow.db')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            project_id INTEGER NOT NULL,
            assignee_id INTEGER,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            label TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    # Seed users
    users = [
        ('alice', 'alice@projectflow.io', 'admin'),
        ('bob', 'bob@projectflow.io', 'member'),
        ('charlie', 'charlie@projectflow.io', 'member'),
        ('diana', 'diana@projectflow.io', 'member'),
        ('evan', 'evan@projectflow.io', 'member'),
        ('fiona', 'fiona@projectflow.io', 'member'),
    ]

    for username, email, role in users:
        existing = cursor.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            password = secrets.token_urlsafe(24)
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, pw_hash, role)
            )

    conn.commit()

    # Seed projects
    alice_id = cursor.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
    bob_id = cursor.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
    charlie_id = cursor.execute("SELECT id FROM users WHERE username='charlie'").fetchone()['id']

    project_count = cursor.execute("SELECT COUNT(*) as c FROM projects").fetchone()['c']
    if project_count == 0:
        projects = [
            ('Q4 Platform Migration', 'Migrate legacy services to cloud-native architecture', alice_id, 'active'),
            ('Mobile App v3', 'Complete redesign of iOS and Android applications', bob_id, 'active'),
            ('API Gateway Implementation', 'Deploy and configure enterprise API gateway', alice_id, 'active'),
            ('Security Audit 2024', 'Annual penetration testing and compliance review', alice_id, 'active'),
            ('Customer Portal Redesign', 'UX overhaul based on user research findings', bob_id, 'in_review'),
            ('Data Pipeline Optimization', 'Improve ETL performance by 40%', charlie_id, 'active'),
            ('SSO Integration', 'SAML 2.0 and OIDC implementation for enterprise clients', alice_id, 'completed'),
            ('Monitoring Stack Upgrade', 'Migrate from Nagios to Prometheus/Grafana', charlie_id, 'active'),
            ('Documentation Overhaul', 'Rewrite all technical docs using new style guide', bob_id, 'active'),
            ('Load Testing Framework', 'Implement automated performance regression testing', charlie_id, 'planning'),
            ('GDPR Compliance Review', 'Data mapping and consent management updates', alice_id, 'active'),
            ('Webhook Delivery System', 'Reliable event delivery with retry logic', bob_id, 'active'),
        ]

        for name, desc, owner_id, status in projects:
            cursor.execute(
                "INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)",
                (name, desc, owner_id, status)
            )

    conn.commit()

    # Seed tasks
    task_count = cursor.execute("SELECT COUNT(*) as c FROM tasks").fetchone()['c']
    if task_count == 0:
        proj1 = cursor.execute("SELECT id FROM projects LIMIT 1").fetchone()['id']
        tasks = [
            ('Design database schema', 'ERD and normalization review', proj1, alice_id, 'done', 'high', '2024-09-15'),
            ('Set up CI/CD pipeline', 'GitHub Actions with staging environment', proj1, bob_id, 'in_progress', 'high', '2024-10-01'),
            ('Write unit tests', 'Target 80% coverage', proj1, charlie_id, 'todo', 'medium', '2024-10-15'),
            ('Performance benchmarking', 'Compare with baseline metrics', proj1, bob_id, 'todo', 'low', '2024-11-01'),
            ('Deploy to staging', 'Full smoke test suite', proj1, alice_id, 'todo', 'high', '2024-10-20'),
        ]
        for title, desc, pid, assignee, status, priority, due in tasks:
            cursor.execute(
                "INSERT INTO tasks (title, description, project_id, assignee_id, status, priority, due_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, desc, pid, assignee, status, priority, due)
            )

    conn.commit()

    # Seed audit logs
    log_count = cursor.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()['c']
    if log_count == 0:
        logs = [
            (alice_id, 'user.login', 'user', alice_id, '10.0.1.5'),
            (alice_id, 'project.create', 'project', 1, '10.0.1.5'),
            (bob_id, 'user.login', 'user', bob_id, '10.0.2.11'),
            (bob_id, 'project.update', 'project', 2, '10.0.2.11'),
            (charlie_id, 'user.login', 'user', charlie_id, '10.0.3.22'),
            (alice_id, 'token.create', 'token', 1, '10.0.1.5'),
            (bob_id, 'task.create', 'task', 1, '10.0.2.11'),
            (charlie_id, 'project.view', 'project', 3, '10.0.3.22'),
        ]
        for uid, action, rtype, rid, ip in logs:
            cursor.execute(
                "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
                (uid, action, rtype, rid, ip)
            )

    conn.commit()
    conn.close()
    logger.info("Database initialized with seed data")
