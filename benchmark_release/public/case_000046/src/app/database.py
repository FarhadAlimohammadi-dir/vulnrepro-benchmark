import sqlite3
import bcrypt
import os
import logging

logger = logging.getLogger(__name__)

_db_path = None

def init_db(db_path):
    global _db_path
    _db_path = db_path
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT,
            is_admin INTEGER DEFAULT 0,
            oauth_provider TEXT,
            oauth_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            is_private INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            ip_address TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS oauth_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            provider TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    conn.commit()
    _seed_data(conn)
    conn.close()
    logger.info("Database initialized at %s", db_path)

def get_db():
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def _seed_data(conn):
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()['cnt'] > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ('alice@example.com', 'alice', 'AlicePass123!', 0),
        ('bob@example.com', 'bob', 'BobPass123!', 0),
        ('charlie@example.com', 'charlie', 'CharliePass123!', 1),
        ('diana@example.com', 'diana', 'DianaPass456!', 0),
        ('eve@example.com', 'eve', 'EvePass789!', 0),
        ('frank@example.com', 'frank', 'FrankPass321!', 0),
        ('grace@corp.com', 'grace', 'GracePass654!', 0),
        ('henry@corp.com', 'henry', 'HenryPass987!', 0),
    ]

    user_ids = {}
    for email, username, password, is_admin in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (email, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (email, username, pw_hash, is_admin)
        )
        user_ids[email] = cursor.lastrowid

    # Seed documents
    documents = [
        (user_ids['alice@example.com'], 'Q3 Financial Report', 'Revenue up 12% this quarter. Confidential.', 1),
        (user_ids['alice@example.com'], 'Project Roadmap', 'New feature set for v2.0 launch in January.', 1),
        (user_ids['alice@example.com'], 'Team Notes', 'Alice personal team meeting notes - internal only.', 1),
        (user_ids['bob@example.com'], 'Product Spec v3', 'Detailed specification for the new API endpoints.', 0),
        (user_ids['bob@example.com'], 'Marketing Copy', 'Draft marketing content for the Q4 campaign.', 0),
        (user_ids['charlie@example.com'], 'Admin Procedures', 'System administration runbooks and escalation paths.', 1),
        (user_ids['charlie@example.com'], 'Incident Response Plan', 'Steps for handling production incidents.', 1),
        (user_ids['diana@example.com'], 'Design Mockups', 'UI mockups for the redesigned dashboard.', 0),
        (user_ids['eve@example.com'], 'API Integration Guide', 'How to integrate with third-party providers.', 0),
        (user_ids['frank@example.com'], 'Budget Forecast', 'Annual budget forecast for engineering team.', 1),
        (user_ids['grace@corp.com'], 'HR Policy Update', 'Updated leave and remote work policies.', 1),
        (user_ids['henry@corp.com'], 'Infrastructure Diagram', 'Network topology and AWS architecture.', 1),
    ]

    for owner_id, title, content, is_private in documents:
        cursor.execute(
            "INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
            (owner_id, title, content, is_private)
        )

    # Seed audit log entries
    audit_entries = [
        (user_ids['alice@example.com'], 'LOGIN', '192.168.1.10', 'method=password'),
        (user_ids['alice@example.com'], 'DOCUMENT_VIEW', '192.168.1.10', 'doc_id=1'),
        (user_ids['bob@example.com'], 'LOGIN', '10.0.0.5', 'method=oauth'),
        (user_ids['charlie@example.com'], 'ADMIN_ACCESS', '10.0.0.1', 'section=users'),
        (user_ids['diana@example.com'], 'LOGIN', '172.16.0.3', 'method=password'),
        (user_ids['eve@example.com'], 'PROFILE_UPDATE', '192.168.2.20', 'fields=username'),
        (user_ids['frank@example.com'], 'LOGIN', '10.10.0.8', 'method=password'),
    ]

    for user_id, action, ip, metadata in audit_entries:
        cursor.execute(
            "INSERT INTO audit_log (user_id, action, ip_address, metadata) VALUES (?, ?, ?, ?)",
            (user_id, action, ip, metadata)
        )

    conn.commit()
    logger.info("Seed data inserted successfully")