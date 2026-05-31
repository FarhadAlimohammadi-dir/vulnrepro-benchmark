import hashlib
import os
import sqlite3
import bcrypt
import logging
from flask_login import UserMixin
from app import get_db

logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, id, username, email, role, created_at):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.created_at = created_at

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['created_at'])
        return None

    @staticmethod
    def get_by_username(username):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return row

    @staticmethod
    def verify_password(username, password):
        row = User.get_by_username(username)
        if not row:
            return None
        if bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            return User(row['id'], row['username'], row['email'], row['role'], row['created_at'])
        return None


class Monitor:
    @staticmethod
    def create(user_id, name, url, description, interval_seconds=300):
        db = get_db()
        cursor = db.execute(
            '''INSERT INTO monitors (user_id, name, url, description, interval_seconds, active, created_at)
               VALUES (?, ?, ?, ?, ?, 1, datetime('now'))''',
            (user_id, name, url, description, interval_seconds)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_by_id(monitor_id):
        db = get_db()
        return db.execute('SELECT * FROM monitors WHERE id = ?', (monitor_id,)).fetchone()

    @staticmethod
    def get_by_user(user_id):
        db = get_db()
        return db.execute(
            'SELECT * FROM monitors WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()

    @staticmethod
    def delete(monitor_id, user_id):
        db = get_db()
        db.execute('DELETE FROM monitors WHERE id = ? AND user_id = ?', (monitor_id, user_id))
        db.commit()

    @staticmethod
    def update(monitor_id, user_id, name, description):
        db = get_db()
        db.execute(
            'UPDATE monitors SET name = ?, description = ? WHERE id = ? AND user_id = ?',
            (name, description, monitor_id, user_id)
        )
        db.commit()


class CheckResult:
    @staticmethod
    def create(monitor_id, status_code, response_time_ms, body_snippet, success):
        db = get_db()
        cursor = db.execute(
            '''INSERT INTO check_results (monitor_id, status_code, response_time_ms, body_snippet, success, checked_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))''',
            (monitor_id, status_code, response_time_ms, body_snippet, success)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_by_monitor(monitor_id, limit=20):
        db = get_db()
        return db.execute(
            'SELECT * FROM check_results WHERE monitor_id = ? ORDER BY checked_at DESC LIMIT ?',
            (monitor_id, limit)
        ).fetchall()

    @staticmethod
    def get_latest(monitor_id):
        db = get_db()
        return db.execute(
            'SELECT * FROM check_results WHERE monitor_id = ? ORDER BY checked_at DESC LIMIT 1',
            (monitor_id,)
        ).fetchone()


def create_tables():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS monitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            interval_seconds INTEGER DEFAULT 300,
            active INTEGER DEFAULT 1,
            last_checked TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS check_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id INTEGER NOT NULL,
            status_code INTEGER,
            response_time_ms INTEGER,
            body_snippet TEXT,
            success INTEGER DEFAULT 0,
            checked_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (monitor_id) REFERENCES monitors(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    db.commit()


def seed_data():
    db = get_db()

    existing = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()
    if existing['cnt'] > 0:
        return

    users = [
        ('alice', 'alice@example.com', 'AlicePass123!', 'admin'),
        ('bob', 'bob@example.com', 'BobPass123!', 'user'),
        ('charlie', 'charlie@example.com', 'CharliePass123!', 'user'),
        ('diana', 'diana@example.com', 'DianaPass456!', 'user'),
        ('eve', 'eve@example.com', 'EvePass789!', 'user'),
    ]

    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, role)
        )
    db.commit()

    alice_id = db.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()['id']
    bob_id = db.execute("SELECT id FROM users WHERE username = 'bob'").fetchone()['id']
    charlie_id = db.execute("SELECT id FROM users WHERE username = 'charlie'").fetchone()['id']

    monitors_data = [
        (alice_id, 'GitHub Status', 'https://www.githubstatus.com', 'GitHub status page', 60),
        (alice_id, 'Company Homepage', 'https://example.com', 'Main website uptime', 300),
        (alice_id, 'API Gateway', 'https://api.example.com/health', 'Production API health', 30),
        (bob_id, 'Personal Blog', 'https://bob-blog.example.net', 'My personal blog', 600),
        (bob_id, 'Portfolio Site', 'https://bobsmith.dev', 'Portfolio uptime check', 3600),
        (bob_id, 'Newsletter Service', 'https://newsletter.bobsmith.dev/ping', 'Newsletter service', 300),
        (charlie_id, 'Client Dashboard', 'https://dashboard.client-corp.com', 'Client dashboard', 120),
        (charlie_id, 'Staging Environment', 'https://staging.client-corp.com', 'Staging uptime', 300),
        (alice_id, 'CDN Health', 'https://cdn.example.com/health', 'CDN endpoint check', 60),
        (bob_id, 'Database Proxy', 'https://dbproxy.example.net/status', 'DB proxy status', 120),
        (charlie_id, 'Worker Queue', 'https://queue.client-corp.com/health', 'Background queue health', 60),
        (alice_id, 'Payment Webhook', 'https://payments.example.com/webhook/health', 'Payment service', 300),
    ]

    for m in monitors_data:
        db.execute(
            '''INSERT INTO monitors (user_id, name, url, description, interval_seconds, active)
               VALUES (?, ?, ?, ?, ?, 1)''',
            m
        )
    db.commit()

    logger.info("Seeded %d users and %d monitors", len(users), len(monitors_data))