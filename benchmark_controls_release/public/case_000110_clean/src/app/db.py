import sqlite3
import os
import hashlib
import logging
import secrets
from flask import g, current_app

logger = logging.getLogger(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None):
    db_conn = g.pop("db", None)
    if db_conn is not None:
        db_conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def seed_password(name: str, fallback_length: int = 24) -> str:
    env_name = f"SEED_PASSWORD_{name.upper()}"
    return hash_password(os.environ.get(env_name) or secrets.token_urlsafe(fallback_length))


def init_db():
    db_path = current_app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            email TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            project_id INTEGER NOT NULL,
            assignee_id INTEGER,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            due_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Database schema initialized")


def seed_data():
    db_path = current_app.config["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    existing = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if existing["cnt"] > 0:
        conn.close()
        return

    logger.info("Seeding initial data...")

    users = [
        ("alice", seed_password("alice"), "Alice Johnson", "alice@taskflow.io", "user"),
        ("bob", seed_password("bob"), "Bob Smith", "bob@taskflow.io", "user"),
        ("charlie", seed_password("charlie"), "Charlie Brown", "charlie@taskflow.io", "user"),
        ("diana", seed_password("initial_admin"), "Diana Prince", "diana@taskflow.io", "admin"),
        ("eve", seed_password("eve"), "Eve Torres", "eve@taskflow.io", "user"),
        ("frank", seed_password("frank"), "Frank Castle", "frank@taskflow.io", "user"),
    ]
    conn.executemany(
        "INSERT INTO users (username, password_hash, display_name, email, role) VALUES (?,?,?,?,?)",
        users,
    )

    projects = [
        ("Website Redesign", "Modernize the company website", 1, "active"),
        ("Mobile App v2", "Second version of the mobile application", 2, "active"),
        ("Data Pipeline", "ETL pipeline for analytics", 3, "active"),
        ("API Gateway", "Centralized API management", 4, "active"),
        ("Security Audit", "Annual security review", 4, "completed"),
    ]
    conn.executemany(
        "INSERT INTO projects (name, description, owner_id, status) VALUES (?,?,?,?)",
        projects,
    )

    tasks_data = [
        ("Design new homepage", "Create mockups for the new homepage layout", 1, 1, "high", "in_progress", "2025-08-01"),
        ("Implement dark mode", "Add dark mode support to all components", 1, 2, "medium", "open", "2025-08-15"),
        ("Write unit tests", "Achieve 80% test coverage", 1, 3, "high", "open", "2025-07-30"),
        ("Setup CI/CD pipeline", "Configure GitHub Actions for automated deployment", 2, 1, "high", "in_progress", "2025-07-25"),
        ("User authentication", "Implement OAuth2 login flow", 2, 2, "high", "open", "2025-08-10"),
        ("Push notifications", "Add FCM push notification support", 2, 3, "medium", "open", "2025-09-01"),
        ("Schema migration", "Migrate from MySQL to PostgreSQL", 3, 4, "high", "open", "2025-08-20"),
        ("Optimize batch jobs", "Reduce processing time by 40%", 3, 1, "medium", "in_progress", "2025-07-28"),
        ("Add rate limiting", "Implement per-user rate limiting", 4, 2, "high", "open", "2025-08-05"),
        ("Update documentation", "Refresh API docs with new endpoints", 4, 3, "low", "open", "2025-09-15"),
        ("Fix memory leak", "Profile and fix memory leak in worker process", 1, 1, "critical", "open", "2025-07-22"),
        ("Accessibility audit", "Ensure WCAG 2.1 AA compliance", 1, 5, "medium", "open", "2025-08-30"),
        ("Performance testing", "Load test with 10k concurrent users", 2, 4, "high", "open", "2025-08-12"),
        ("Data retention policy", "Implement automated data purging", 3, 3, "medium", "open", "2025-09-10"),
        ("Webhook integration", "Add outbound webhook support for events", 4, 2, "medium", "open", "2025-08-25"),
    ]
    conn.executemany(
        "INSERT INTO tasks (title, description, project_id, assignee_id, priority, status, due_date) VALUES (?,?,?,?,?,?,?)",
        tasks_data,
    )

    comments_data = [
        (1, 2, "Mockups look great! Minor tweaks needed on mobile breakpoints."),
        (1, 3, "Approved the color scheme. Let's proceed."),
        (4, 1, "GitHub Actions configured. Waiting for code review."),
        (5, 3, "OAuth2 provider selected. Starting implementation."),
        (8, 4, "Profiling shows the bottleneck is in the aggregation step."),
        (11, 2, "Reproduced the issue. It's in the event listener cleanup."),
    ]
    conn.executemany(
        "INSERT INTO comments (task_id, author_id, content) VALUES (?,?,?)",
        comments_data,
    )

    conn.commit()
    conn.close()
    logger.info("Seed data inserted successfully")
