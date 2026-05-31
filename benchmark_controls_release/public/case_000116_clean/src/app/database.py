import sqlite3
import os
import bcrypt
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'docshare.db')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = get_db()
    try:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                declared_type TEXT DEFAULT 'text/plain',
                visibility TEXT DEFAULT 'private',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
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

            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                shared_with TEXT NOT NULL,
                permission TEXT DEFAULT 'read',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );
        ''')
        db.commit()

        # Seed users if not present
        existing = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()
        if existing['cnt'] == 0:
            _seed_data(db)

    except Exception as e:
        logger.error(f"DB init error: {e}")
    finally:
        db.close()


def _seed_data(db):
    users = [
        ('alice', 'alice@docshare.io', 'AlicePass123!', 'admin'),
        ('bob', 'bob@docshare.io', 'BobPass123!', 'user'),
        ('charlie', 'charlie@docshare.io', 'CharliePass123!', 'user'),
        ('diana', 'diana@docshare.io', 'DianaPass456!', 'user'),
        ('eve', 'eve@docshare.io', 'EvePass789!', 'user'),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor = db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, role)
        )
        user_ids[username] = cursor.lastrowid

    # Seed documents
    docs = [
        (user_ids['alice'], 'Q3 Budget Report', 'Total expenditure for Q3: $1,234,567\nRevenue: $2,100,000\nProfit: $865,433', 'text/plain', 'private'),
        (user_ids['alice'], 'Team Meeting Notes', 'Attendees: Alice, Bob, Charlie\nTopics: Roadmap, Hiring, Budget\nAction items: TBD', 'text/plain', 'public'),
        (user_ids['bob'], 'Project Proposal', 'Project: DocShare Enterprise\nTimeline: 6 months\nBudget: $500,000', 'text/plain', 'public'),
        (user_ids['bob'], 'Technical Spec v2', 'Architecture: Microservices\nStack: Python/Flask + React\nDB: PostgreSQL', 'text/plain', 'private'),
        (user_ids['charlie'], 'Marketing Campaign', 'Campaign: Q4 Launch\nBudget: $50,000\nTarget: SMBs', 'text/plain', 'public'),
        (user_ids['charlie'], 'Vendor Contracts', 'Vendor: AcmeCorp\nContract value: $120,000\nExpiry: 2025-12-31', 'text/plain', 'private'),
        (user_ids['diana'], 'Research Notes', 'Topic: Competitive Analysis\nCompetitors: DocuSign, Box, Dropbox', 'text/plain', 'public'),
        (user_ids['eve'], 'Legal Review', 'Document: ToS v3\nReviewed by: LegalTeam\nStatus: Approved', 'text/plain', 'private'),
        (user_ids['alice'], 'Architecture Diagram Notes', 'See confluence for diagram\nKey components: API Gateway, Auth Service, Storage', 'text/plain', 'public'),
        (user_ids['bob'], 'Sprint Retrospective', 'What went well: CI/CD pipeline\nWhat to improve: Code review turnaround', 'text/plain', 'public'),
    ]

    for owner_id, title, content, dtype, visibility in docs:
        db.execute(
            'INSERT INTO documents (owner_id, title, content, declared_type, visibility) VALUES (?, ?, ?, ?, ?)',
            (owner_id, title, content, dtype, visibility)
        )

    db.commit()
    logger.info("Seeded initial data")