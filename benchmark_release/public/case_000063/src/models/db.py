import sqlite3
import os
import bcrypt
import logging
from flask import g, current_app

logger = logging.getLogger(__name__)

DATABASE = os.environ.get("DATABASE_PATH", "/app/data/projecthub.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            DATABASE,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def init_db():
    db = get_db()
    logger.info("Initializing database schema...")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS project_members (
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'contributor',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            assignee_id INTEGER,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            webhook_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    """)

    _seed_data(db)
    db.commit()
    logger.info("Database initialization complete.")


def _seed_data(db):
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ("alice@projecthub.io", "AlicePass123!", "Alice Thornton", "admin"),
        ("bob@projecthub.io", "BobPass123!", "Bob Martinez", "member"),
        ("charlie@projecthub.io", "CharliePass123!", "Charlie Nguyen", "viewer"),
        ("diana@projecthub.io", "DianaPass456!", "Diana Okafor", "member"),
        ("evan@projecthub.io", "EvanPass789!", "Evan Kowalski", "member"),
    ]

    user_ids = []
    for email, password, full_name, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = db.execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (email, pw_hash, full_name, role)
        )
        user_ids.append(cur.lastrowid)

    alice_id, bob_id, charlie_id, diana_id, evan_id = user_ids

    projects_data = [
        ("Website Redesign", "Complete overhaul of the marketing site", alice_id, "active"),
        ("Mobile App v2", "iOS and Android release", bob_id, "active"),
        ("Data Pipeline", "ETL pipeline for analytics", alice_id, "active"),
        ("API Gateway", "Unified API gateway project", diana_id, "archived"),
        ("Security Audit", "Q4 compliance review", alice_id, "active"),
    ]

    project_ids = []
    for name, desc, owner, status in projects_data:
        cur = db.execute(
            "INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)",
            (name, desc, owner, status)
        )
        project_ids.append(cur.lastrowid)

    members = [
        (project_ids[0], alice_id, "owner"),
        (project_ids[0], bob_id, "contributor"),
        (project_ids[0], charlie_id, "viewer"),
        (project_ids[1], bob_id, "owner"),
        (project_ids[1], diana_id, "contributor"),
        (project_ids[2], alice_id, "owner"),
        (project_ids[2], evan_id, "contributor"),
        (project_ids[3], diana_id, "owner"),
        (project_ids[4], alice_id, "owner"),
        (project_ids[4], charlie_id, "viewer"),
    ]
    for pid, uid, role in members:
        db.execute(
            "INSERT OR IGNORE INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
            (pid, uid, role)
        )

    tasks_data = [
        (project_ids[0], "Design mockups", "Create Figma mockups for homepage", alice_id, "done", "high"),
        (project_ids[0], "Implement nav", "Responsive navigation bar", bob_id, "in_progress", "high"),
        (project_ids[0], "SEO audit", "Review meta tags and structured data", charlie_id, "todo", "medium"),
        (project_ids[1], "Auth module", "JWT-based authentication flow", bob_id, "in_progress", "critical"),
        (project_ids[1], "Push notifications", "Firebase integration", diana_id, "todo", "medium"),
        (project_ids[1], "App store listing", "Screenshots and descriptions", bob_id, "todo", "low"),
        (project_ids[2], "Kafka setup", "Configure Kafka cluster", evan_id, "done", "high"),
        (project_ids[2], "Transform layer", "Data normalization logic", alice_id, "in_progress", "high"),
        (project_ids[2], "Monitoring", "Grafana dashboards for pipeline", evan_id, "todo", "medium"),
        (project_ids[4], "Dependency scan", "Run npm audit and Snyk", alice_id, "in_progress", "high"),
        (project_ids[4], "Pen test report", "Summarize findings from external audit", alice_id, "todo", "critical"),
        (project_ids[4], "Access review", "Quarterly IAM permissions review", charlie_id, "todo", "high"),
    ]
    for pid, title, desc, assignee, status, priority in tasks_data:
        db.execute(
            "INSERT INTO tasks (project_id, title, description, assignee_id, status, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, title, desc, assignee, status, priority)
        )

    integrations = [
        (project_ids[0], "GitHub", "https://hooks.github.com/services/abc123", 1),
        (project_ids[1], "Slack", "https://hooks.slack.com/services/xyz789", 1),
        (project_ids[2], "PagerDuty", "https://events.pagerduty.com/v2/enqueue", 1),
        (project_ids[4], "Jira", "https://projecthub.atlassian.net/webhook/abc", 0),
    ]
    for pid, svc, url, active in integrations:
        db.execute(
            "INSERT INTO api_integrations (project_id, service_name, webhook_url, is_active) VALUES (?, ?, ?, ?)",
            (pid, svc, url, active)
        )

    audit_entries = [
        (alice_id, "user.login", "user", alice_id, "Login from 10.0.0.1", "10.0.0.1"),
        (alice_id, "project.create", "project", project_ids[0], "Created Website Redesign", "10.0.0.1"),
        (bob_id, "user.login", "user", bob_id, "Login from 10.0.0.2", "10.0.0.2"),
        (bob_id, "task.update", "task", 2, "Status changed to in_progress", "10.0.0.2"),
        (diana_id, "user.login", "user", diana_id, "Login from 192.168.1.5", "192.168.1.5"),
    ]
    for uid, action, rtype, rid, details, ip in audit_entries:
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, action, rtype, rid, details, ip)
        )

    logger.info("Seed data inserted successfully.")