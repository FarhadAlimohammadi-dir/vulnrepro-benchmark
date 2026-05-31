import sqlite3
import bcrypt
import os
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', 'data/acmedocs.db')


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, is_admin, is_corporate, created_at):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.is_admin = bool(is_admin)
        self.is_corporate = bool(is_corporate)
        self.created_at = created_at

    def get_id(self):
        return str(self.id)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            is_corporate INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            is_corporate INTEGER DEFAULT 0,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    seed_data(cur, conn)
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def seed_data(cur, conn):
    existing = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    users = [
        ('alice', 'alice@acmecorp.com', 'AlicePass123!', 1, 1),
        ('bob', 'bob@gmail.com', 'BobPass123!', 0, 0),
        ('charlie', 'charlie@acmecorp.com', 'CharliePass123!', 0, 1),
        ('diana', 'diana@acmecorp.com', 'DianaPass456!', 0, 1),
        ('eve', 'eve@yahoo.com', 'EvePass789!', 0, 0),
        ('frank', 'frank@acmecorp.com', 'FrankPass321!', 0, 1),
        ('grace', 'grace@hotmail.com', 'GracePass654!', 0, 0),
        ('henry', 'henry@acmecorp.com', 'HenryPass987!', 0, 1),
        ('ivan', 'ivan@protonmail.com', 'IvanPass111!', 0, 0),
        ('julia', 'julia@acmecorp.com', 'JuliaPass222!', 0, 1),
    ]

    for username, email, password, is_admin, is_corporate in users:
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO users (username, email, password_hash, is_admin, is_corporate) VALUES (?, ?, ?, ?, ?)",
            (username, email, pw_hash, is_admin, is_corporate)
        )

    # Seed corporate documents
    corporate_docs = [
        ('Q3 Financial Report 2024', 'Revenue: $4.2M. EBITDA margin: 23%. YoY growth: 18%.', 1, 1, 'finance'),
        ('Employee Handbook v4.2', 'All employees must complete compliance training by Dec 31.', 1, 1, 'hr'),
        ('Security Policy 2024', 'MFA required for all internal systems as of Jan 2024.', 1, 1, 'security'),
        ('Product Roadmap H2 2024', 'Launch mobile app Q3, expand EU data centers Q4.', 3, 1, 'product'),
        ('Board Meeting Minutes Oct 2024', 'Approved Series B extension. New hires in engineering.', 1, 1, 'governance'),
        ('Vendor Contracts Summary', 'AWS: $180k/yr. Salesforce: $42k/yr. Jira: $12k/yr.', 4, 1, 'legal'),
        ('Engineering Runbook v2', 'On-call rotation: follow PagerDuty escalation policy.', 6, 1, 'engineering'),
        ('Marketing Strategy 2025', 'Focus on SMB segment. Budget: $500k for digital ads.', 8, 1, 'marketing'),
    ]

    for title, content, owner_id, is_corp, category in corporate_docs:
        cur.execute(
            "INSERT INTO documents (title, content, owner_id, is_corporate, category) VALUES (?, ?, ?, ?, ?)",
            (title, content, owner_id, is_corp, category)
        )

    # Public documents
    public_docs = [
        ('Company Overview', 'ACME Corp - Leading provider of enterprise document solutions.', 1, 0, 'general'),
        ('Press Release Q3', 'ACME Corp announces record revenue for Q3 2024.', 1, 0, 'general'),
        ('Open Source Policy', 'ACME Corp supports open source. See github.com/acmecorp.', 3, 0, 'general'),
    ]

    for title, content, owner_id, is_corp, category in public_docs:
        cur.execute(
            "INSERT INTO documents (title, content, owner_id, is_corporate, category) VALUES (?, ?, ?, ?, ?)",
            (title, content, owner_id, is_corp, category)
        )

    logger.info("Seed data inserted")


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(*row)
    return None


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row:
        return User(*row)
    return None


def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if row:
        return User(*row)
    return None


def get_db():
    return get_connection()


def log_audit(user_id, action, detail, ip_address=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (user_id, action, detail, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, action, detail, ip_address)
    )
    conn.commit()
    conn.close()