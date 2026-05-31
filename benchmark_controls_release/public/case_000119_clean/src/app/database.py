import sqlite3
import os
import bcrypt
from flask import g

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/projecthub.db')


def get_db():
    if 'db' not in g._get_current_object().__dict__:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        g.db = conn
    return g.db


def get_raw_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            owner_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS project_members (
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'viewer',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            rendered_html TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS widget_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            content_html TEXT NOT NULL,
            widget_type TEXT DEFAULT 'dashboard',
            posted_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed users
    users = [
        ('alice', 'alice@projecthub.local', 'AlicePass123!', 'admin'),
        ('bob', 'bob@projecthub.local', 'BobPass123!', 'member'),
        ('charlie', 'charlie@projecthub.local', 'CharliePass123!', 'member'),
        ('diana', 'diana@projecthub.local', 'DianaPass123!', 'member'),
        ('eve', 'eve@projecthub.local', 'EvePass123!', 'viewer'),
    ]

    for username, email, password, role in users:
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (username, email, pw_hash, role)
            )

    conn.commit()

    # Seed projects
    alice_id = conn.execute('SELECT id FROM users WHERE username = ?', ('alice',)).fetchone()['id']
    bob_id = conn.execute('SELECT id FROM users WHERE username = ?', ('bob',)).fetchone()['id']

    projects_data = [
        ('Website Redesign', 'Complete overhaul of the company website', 'active', alice_id),
        ('Mobile App v2', 'Second version of the mobile application', 'active', bob_id),
        ('API Gateway Migration', 'Moving from monolith to microservices', 'planning', alice_id),
        ('Data Pipeline', 'ETL pipeline for analytics', 'completed', bob_id),
        ('Security Audit Q4', 'Quarterly security review', 'active', alice_id),
        ('Customer Portal', 'Self-service portal for enterprise clients', 'planning', bob_id),
        ('CI/CD Overhaul', 'Modernizing deployment pipeline', 'active', alice_id),
    ]

    for name, desc, status, owner in projects_data:
        existing = conn.execute('SELECT id FROM projects WHERE name = ?', (name,)).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO projects (name, description, status, owner_id) VALUES (?, ?, ?, ?)',
                (name, desc, status, owner)
            )

    conn.commit()

    # Seed comments
    p1 = conn.execute('SELECT id FROM projects WHERE name = ?', ('Website Redesign',)).fetchone()
    if p1:
        comments = [
            (p1['id'], alice_id, 'Initial scope has been approved by stakeholders.'),
            (p1['id'], bob_id, 'Design mockups are ready for review.'),
            (p1['id'], alice_id, 'Accessibility requirements updated per WCAG 2.1 AA.'),
        ]
        for proj_id, user_id, content in comments:
            conn.execute(
                'INSERT OR IGNORE INTO comments (project_id, user_id, content, rendered_html) VALUES (?, ?, ?, ?)',
                (proj_id, user_id, content, f'<p>{content}</p>')
            )

    conn.commit()

    # Seed audit log
    audit_entries = [
        (alice_id, 'LOGIN', 'user', alice_id, '10.0.0.1'),
        (bob_id, 'LOGIN', 'user', bob_id, '10.0.0.2'),
        (alice_id, 'CREATE', 'project', 1, '10.0.0.1'),
        (bob_id, 'UPDATE', 'project', 2, '10.0.0.2'),
        (alice_id, 'DELETE', 'comment', 5, '10.0.0.1'),
    ]
    for user_id, action, rtype, rid, ip in audit_entries:
        conn.execute(
            'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
            (user_id, action, rtype, rid, ip)
        )

    conn.commit()
    conn.close()