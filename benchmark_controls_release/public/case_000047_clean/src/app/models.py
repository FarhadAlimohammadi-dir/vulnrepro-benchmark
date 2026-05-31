import sqlite3
import os
import secrets
import bcrypt
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_db(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(database_path):
    conn = get_db(database_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            created_at TEXT NOT NULL,
            last_login TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'private',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            tags TEXT DEFAULT '',
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS document_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL DEFAULT 'read',
            shared_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(document_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hint TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    # Seed initial users if not present
    users = [
        ('alice', 'alice@collabify.io', 'admin'),
        ('bob', 'bob@collabify.io', 'editor'),
        ('charlie', 'charlie@collabify.io', 'viewer'),
        ('diana', 'diana@collabify.io', 'editor'),
        ('eve', 'eve@collabify.io', 'viewer'),
    ]

    now = datetime.utcnow().isoformat()
    for username, email, role in users:
        existing = cursor.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            password = secrets.token_urlsafe(24)
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, email, pw_hash, role, now)
            )

    conn.commit()

    # Seed documents
    alice_id = cursor.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
    bob_id = cursor.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
    charlie_id = cursor.execute("SELECT id FROM users WHERE username='charlie'").fetchone()['id']

    doc_count = cursor.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()['cnt']
    if doc_count == 0:
        sample_docs = [
            (alice_id, 'Q4 2023 Planning', 'Strategic initiatives for Q4 including product roadmap and resource allocation.', 'internal', 'planning,q4,strategy'),
            (alice_id, 'Security Policy v2.1', 'Updated security policies for all staff. Mandatory reading before system access.', 'internal', 'security,policy,compliance'),
            (alice_id, 'Admin Configuration Guide', 'Step-by-step guide for configuring the Collabify platform for enterprise deployments.', 'private', 'admin,config,enterprise'),
            (bob_id, 'API Integration Notes', 'Notes on integrating third-party APIs with the document management system.', 'internal', 'api,integration,dev'),
            (bob_id, 'Release Notes v3.2', 'Bug fixes and feature additions in the 3.2 release cycle.', 'public', 'release,changelog'),
            (bob_id, 'Data Migration Plan', 'Plan for migrating legacy document storage to new S3-compatible backend.', 'internal', 'migration,data,infra'),
            (charlie_id, 'Onboarding Checklist', 'New employee onboarding document checklist and process guide.', 'public', 'hr,onboarding'),
            (charlie_id, 'Team Meeting Notes - Nov', 'Notes from November team sync meetings.', 'internal', 'meetings,notes'),
            (alice_id, 'Incident Response Runbook', 'Procedures for handling production incidents and escalation paths.', 'private', 'ops,incident,runbook'),
            (bob_id, 'Frontend Style Guide', 'Design system and component library documentation.', 'public', 'design,frontend,ui'),
            (alice_id, 'User Management Procedures', 'How to create, modify and deactivate user accounts in Collabify.', 'private', 'admin,users,procedures'),
            (charlie_id, 'FAQ - Common Issues', 'Frequently asked questions and known workarounds for common issues.', 'public', 'support,faq'),
        ]

        for owner_id, title, content, visibility, tags in sample_docs:
            cursor.execute(
                """INSERT INTO documents (title, content, owner_id, visibility, created_at, updated_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, content, owner_id, visibility, now, now, tags)
            )

        conn.commit()

        # Seed some comments
        docs = cursor.execute("SELECT id FROM documents LIMIT 5").fetchall()
        sample_comments = [
            "Great document, very thorough!",
            "Please update the section on API keys.",
            "This needs review before the Q4 deadline.",
            "I've added some notes in the appendix.",
            "Can we schedule a meeting to discuss this?",
        ]
        for i, doc in enumerate(docs):
            cursor.execute(
                "INSERT INTO comments (document_id, user_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (doc['id'], alice_id if i % 2 == 0 else bob_id, sample_comments[i], now, now)
            )

        # Seed audit log entries
        audit_entries = [
            (alice_id, 'LOGIN', 'user', alice_id, 'Successful login', '10.0.0.1'),
            (bob_id, 'LOGIN', 'user', bob_id, 'Successful login', '10.0.0.2'),
            (alice_id, 'CREATE', 'document', 1, 'Created Q4 Planning doc', '10.0.0.1'),
            (bob_id, 'UPDATE', 'document', 4, 'Updated API integration notes', '10.0.0.2'),
            (alice_id, 'SHARE', 'document', 3, 'Shared with bob', '10.0.0.1'),
            (charlie_id, 'VIEW', 'document', 7, 'Viewed onboarding checklist', '10.0.0.3'),
            (alice_id, 'DELETE', 'document', None, 'Attempted delete of archived doc', '10.0.0.1'),
            (bob_id, 'EXPORT', 'document', 5, 'Exported release notes as PDF', '10.0.0.2'),
        ]
        for uid, action, rtype, rid, details, ip in audit_entries:
            cursor.execute(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, action, rtype, rid, details, ip, now)
            )

        conn.commit()

    conn.close()
    logger.info("Database initialized with seed data")
