import sqlite3
import bcrypt
import os
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/pulsecheck.db')


def get_db(path=None):
    db_path = path or DATABASE_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


class User(UserMixin):
    def __init__(self, id, username, email, role='user'):
        self.id = id
        self.username = username
        self.email = email
        self.role = role


def get_user_by_id(user_id, path=None):
    conn = get_db(path)
    try:
        row = conn.execute(
            'SELECT id, username, email, role FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'])
    finally:
        conn.close()
    return None


def get_user_by_username(username, path=None):
    conn = get_db(path)
    try:
        row = conn.execute(
            'SELECT id, username, email, password_hash, role FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        return row
    finally:
        conn.close()


def db_init(path=None):
    conn = get_db(path)
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS uptime_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                custom_headers TEXT DEFAULT '{}',
                check_interval INTEGER DEFAULT 60,
                timeout INTEGER DEFAULT 10,
                expected_status INTEGER DEFAULT 200,
                content_match TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                response_code INTEGER,
                response_time_ms INTEGER,
                response_body TEXT,
                error_message TEXT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (check_id) REFERENCES uptime_checks(id)
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                FOREIGN KEY (check_id) REFERENCES uptime_checks(id)
            );

            CREATE TABLE IF NOT EXISTS alert_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                threshold INTEGER DEFAULT 3,
                notification_email TEXT,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (check_id) REFERENCES uptime_checks(id)
            );
        ''')
        conn.commit()
        logger.info('Database schema initialized')
    finally:
        conn.close()


def seed_data(path=None):
    conn = get_db(path)
    try:
        existing = conn.execute('SELECT COUNT(*) as cnt FROM users').fetchone()
        if existing['cnt'] > 0:
            logger.info('Database already seeded, skipping')
            return

        users = [
            ('alice', 'alice@pulsecheck.io', 'AlicePass123!', 'admin'),
            ('bob', 'bob@pulsecheck.io', 'BobPass123!', 'user'),
            ('charlie', 'charlie@pulsecheck.io', 'CharliePass123!', 'user'),
        ]

        user_ids = {}
        for username, email, password, role in users:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor = conn.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (username, email, pw_hash, role)
            )
            user_ids[username] = cursor.lastrowid

        checks = [
            (user_ids['alice'], 'Production API', 'https://api.example.com/health', 'GET', 30, 200),
            (user_ids['alice'], 'Marketing Site', 'https://www.example.com', 'GET', 60, 200),
            (user_ids['alice'], 'Auth Service', 'https://auth.example.com/ping', 'GET', 30, 200),
            (user_ids['alice'], 'Payment Gateway', 'https://pay.example.com/status', 'GET', 60, 200),
            (user_ids['alice'], 'CDN Health', 'https://cdn.example.com/health', 'GET', 120, 200),
            (user_ids['bob'], 'Dev API', 'https://dev-api.example.com/health', 'GET', 60, 200),
            (user_ids['bob'], 'Staging Site', 'https://staging.example.com', 'GET', 60, 200),
            (user_ids['bob'], 'Webhook Receiver', 'https://hooks.example.com/health', 'GET', 30, 200),
            (user_ids['charlie'], 'Legacy API v1', 'https://api-v1.example.com/ping', 'GET', 120, 200),
            (user_ids['charlie'], 'File Storage', 'https://files.example.com/health', 'GET', 60, 200),
            (user_ids['charlie'], 'Email Service', 'https://mail.example.com/status', 'GET', 60, 200),
            (user_ids['alice'], 'Data Pipeline', 'https://pipeline.example.com/health', 'GET', 300, 200),
            (user_ids['bob'], 'Search Service', 'https://search.example.com/health', 'GET', 60, 200),
            (user_ids['charlie'], 'Admin Panel', 'https://admin.example.com/health', 'GET', 30, 200),
            (user_ids['alice'], 'Metrics Collector', 'https://metrics.example.com/ping', 'GET', 30, 200),
        ]

        check_ids = []
        for user_id, name, url, method, interval, expected_status in checks:
            cursor = conn.execute(
                '''INSERT INTO uptime_checks
                   (user_id, name, url, method, check_interval, expected_status, active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)''',
                (user_id, name, url, method, interval, expected_status)
            )
            check_ids.append(cursor.lastrowid)

        incidents_data = [
            (check_ids[0], 'Production API degraded performance', 'high', 'resolved'),
            (check_ids[1], 'Marketing site 503 errors', 'medium', 'resolved'),
            (check_ids[5], 'Dev API unreachable', 'low', 'resolved'),
            (check_ids[2], 'Auth service timeout', 'high', 'open'),
            (check_ids[8], 'Legacy API elevated error rate', 'medium', 'open'),
            (check_ids[3], 'Payment gateway SSL cert expiring', 'high', 'resolved'),
            (check_ids[11], 'Data pipeline stalled', 'medium', 'resolved'),
            (check_ids[9], 'File storage quota warning', 'low', 'open'),
            (check_ids[6], 'Staging site maintenance window', 'low', 'resolved'),
            (check_ids[14], 'Metrics collector reconnect loop', 'medium', 'resolved'),
        ]

        for check_id, title, severity, status in incidents_data:
            conn.execute(
                'INSERT INTO incidents (check_id, title, severity, status) VALUES (?, ?, ?, ?)',
                (check_id, title, severity, status)
            )

        conn.commit()
        logger.info(f'Seeded {len(users)} users, {len(checks)} checks, {len(incidents_data)} incidents')
    finally:
        conn.close()