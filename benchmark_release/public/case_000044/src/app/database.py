import os
import sqlite3
import bcrypt
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/projecthub.db')


def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            full_name TEXT,
            department TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            access_level TEXT DEFAULT 'read',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(user_id, project_id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            due_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        );
    """)

    conn.commit()

    # Seed users
    seed_users = [
        ('alice', 'alice@projecthub.io', 'AlicePass123!', 'admin', 'Alice Johnson', 'Engineering'),
        ('bob', 'bob@projecthub.io', 'BobPass123!', 'user', 'Bob Smith', 'Marketing'),
        ('charlie', 'charlie@projecthub.io', 'CharliePass123!', 'user', 'Charlie Brown', 'Design'),
        ('diana', 'diana@projecthub.io', 'DianaPass123!', 'user', 'Diana Prince', 'Engineering'),
        ('eve', 'eve@projecthub.io', 'EvePass123!', 'user', 'Eve Torres', 'Sales'),
        ('frank', 'frank@projecthub.io', 'FrankPass123!', 'user', 'Frank Castle', 'HR'),
        ('grace', 'grace@projecthub.io', 'GracePass123!', 'user', 'Grace Hopper', 'Engineering'),
        ('henry', 'henry@projecthub.io', 'HenryPass123!', 'user', 'Henry Ford', 'Operations'),
        ('iris', 'iris@projecthub.io', 'IrisPass123!', 'user', 'Iris West', 'Finance'),
        ('jack', 'jack@projecthub.io', 'JackPass123!', 'user', 'Jack Ryan', 'Legal'),
    ]

    for username, email, password, role, full_name, dept in seed_users:
        existing = cur.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute(
                "INSERT INTO users (username, email, password_hash, role, full_name, department) VALUES (?, ?, ?, ?, ?, ?)",
                (username, email, pw_hash, role, full_name, dept)
            )

    conn.commit()

    # Seed projects
    alice_id = cur.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()
    bob_id = cur.execute("SELECT id FROM users WHERE username = 'bob'").fetchone()

    if alice_id and bob_id:
        seed_projects = [
            ('Platform Rewrite', 'Complete backend platform rewrite for Q4', alice_id[0], 'active'),
            ('Marketing Campaign Q1', 'New product launch marketing materials', bob_id[0], 'active'),
            ('Design System v2', 'Update component library', alice_id[0], 'planning'),
            ('Data Pipeline', 'ETL pipeline for analytics', alice_id[0], 'active'),
            ('Mobile App', 'iOS and Android application', bob_id[0], 'planning'),
        ]
        for name, desc, owner, status in seed_projects:
            existing = cur.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
            if not existing:
                cur.execute(
                    "INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)",
                    (name, desc, owner, status)
                )

    conn.commit()

    # Seed audit logs
    seed_logs = [
        (1, 'user.login', 'user', 1, 'Successful login', '10.0.0.1'),
        (1, 'project.create', 'project', 1, 'Created Platform Rewrite project', '10.0.0.1'),
        (2, 'user.login', 'user', 2, 'Successful login', '10.0.0.2'),
        (2, 'project.view', 'project', 1, 'Viewed project details', '10.0.0.2'),
        (1, 'user.create', 'user', 3, 'Created user charlie', '10.0.0.1'),
        (3, 'user.login', 'user', 3, 'Successful login', '10.0.0.3'),
        (1, 'project.update', 'project', 2, 'Updated project status', '10.0.0.1'),
        (4, 'user.login', 'user', 4, 'Successful login', '10.0.0.4'),
        (1, 'audit.view', 'audit_log', None, 'Admin viewed audit logs', '10.0.0.1'),
        (5, 'user.login', 'user', 5, 'Successful login', '10.0.0.5'),
    ]

    for user_id, action, resource_type, resource_id, details, ip in seed_logs:
        cur.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, resource_type, resource_id, details, ip)
        )

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")