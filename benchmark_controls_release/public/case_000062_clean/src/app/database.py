import os
import sqlite3
import hashlib
import logging
import secrets

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DATABASE_PATH', 'data/docstore.db')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


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
            role TEXT NOT NULL DEFAULT 'user',
            api_token TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'draft',
            internal_ref TEXT NOT NULL,
            share_token TEXT,
            is_public INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
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

        CREATE TABLE IF NOT EXISTS document_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            shared_with_id INTEGER NOT NULL,
            permission TEXT DEFAULT 'read',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (shared_with_id) REFERENCES users(id)
        );
    """)

    conn.commit()

    # Seed users if not present
    existing = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        _seed_data(cursor)
        conn.commit()
        logger.info("Database seeded with initial data")

    conn.close()


def _seed_data(cursor):
    import bcrypt

    users = [
        ('alice', 'alice@docstore.example.com', 'AlicePass123!', 'user'),
        ('bob', 'bob@docstore.example.com', 'BobPass123!', 'user'),
        ('charlie', 'charlie@docstore.example.com', 'CharliePass123!', 'admin'),
        ('diana', 'diana@docstore.example.com', 'Diana!2024', 'user'),
        ('eve', 'eve@docstore.example.com', 'Eve@Secure9', 'user'),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        api_token = secrets.token_hex(24)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, api_token) VALUES (?,?,?,?,?)",
            (username, email, pw_hash, role, api_token)
        )
        user_ids[username] = cursor.lastrowid

    documents = [
        (user_ids['alice'], 'Q3 Financial Report', 'Revenue increased by 12% in Q3. Operating costs remain stable.', 'finance', 'published'),
        (user_ids['alice'], 'Product Roadmap 2024', 'Phase 1: Core features. Phase 2: Enterprise integrations. Phase 3: Mobile.', 'strategy', 'published'),
        (user_ids['alice'], 'API Integration Guide', 'Steps to integrate with the REST API using OAuth2.0 bearer tokens.', 'technical', 'published'),
        (user_ids['alice'], 'Internal Security Audit Notes', 'Review findings from the third-party penetration test. Internal only.', 'security', 'draft'),
        (user_ids['bob'], 'Marketing Campaign Brief', 'Summer campaign targeting SMBs. Budget: $50k. Timeline: 6 weeks.', 'marketing', 'published'),
        (user_ids['bob'], 'Customer Onboarding SOP', 'Standard operating procedure for new enterprise customer onboarding.', 'operations', 'published'),
        (user_ids['bob'], 'Vendor Comparison Matrix', 'Comparing AWS, GCP, Azure for our new infrastructure migration.', 'technical', 'draft'),
        (user_ids['charlie'], 'System Architecture Overview', 'Microservices diagram and data flow documentation.', 'technical', 'published'),
        (user_ids['charlie'], 'Incident Response Playbook', 'Steps for handling security incidents, outages, and data issues.', 'operations', 'published'),
        (user_ids['charlie'], 'Board Meeting Presentation', 'Q4 objectives and OKR review for executive stakeholders.', 'strategy', 'published'),
        (user_ids['diana'], 'UX Research Summary', 'User interviews with 20 participants. Key pain points identified.', 'research', 'published'),
        (user_ids['diana'], 'Accessibility Compliance Report', 'WCAG 2.1 AA compliance review for the main product dashboard.', 'compliance', 'published'),
        (user_ids['eve'], 'Data Retention Policy', 'Policy document outlining data retention periods per regulation.', 'compliance', 'published'),
        (user_ids['eve'], 'GDPR Processing Records', 'Records of processing activities as required by Article 30.', 'compliance', 'draft'),
        (user_ids['alice'], 'Infrastructure Cost Analysis', 'Monthly breakdown of cloud infrastructure spend and optimization opportunities.', 'finance', 'draft'),
    ]

    for owner_id, title, content, category, status in documents:
        internal_ref = 'DOC-' + secrets.token_hex(8).upper()
        share_token = secrets.token_urlsafe(16)
        cursor.execute(
            """INSERT INTO documents (owner_id, title, content, category, status, internal_ref, share_token, is_public)
               VALUES (?,?,?,?,?,?,?,?)""",
            (owner_id, title, content, category, status, internal_ref, share_token, 1 if status == 'published' else 0)
        )

    for i in range(1, 6):
        cursor.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?,?,?,?,?)",
            (i, 'login', 'session', None, '10.0.0.' + str(i))
        )