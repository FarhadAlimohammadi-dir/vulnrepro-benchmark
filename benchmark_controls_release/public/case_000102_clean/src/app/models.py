import os
import sqlite3
import hashlib
import logging
from datetime import datetime
from flask import current_app
from flask_login import UserMixin

logger = logging.getLogger(__name__)


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin

    def get_id(self):
        return str(self.id)


def hash_password(password: str) -> str:
    salt = "apiforge_static_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def get_user_by_id(user_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, is_admin FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], bool(row['is_admin']))
        return None
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash, is_admin FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        return row
    finally:
        conn.close()


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mock_endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                response_body TEXT NOT NULL,
                content_type TEXT DEFAULT 'application/json',
                status_code INTEGER DEFAULT 200,
                description TEXT,
                hit_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (endpoint_id) REFERENCES mock_endpoints(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL,
                label TEXT,
                last_used TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        conn.commit()
        logger.info("Database schema initialized")
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        if existing['cnt'] > 0:
            return

        users = [
            ('alice', 'alice@apiforge.dev', hash_password('AlicePass123!'), 1),
            ('bob', 'bob@apiforge.dev', hash_password('BobPass123!'), 0),
            ('charlie', 'charlie@apiforge.dev', hash_password('CharliePass123!'), 0),
            ('diana', 'diana@apiforge.dev', hash_password('DianaPass456!'), 0),
            ('eve', 'eve@apiforge.dev', hash_password('EvePass789!'), 0),
        ]
        conn.executemany(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            users
        )

        endpoints = [
            (2, 'User Profile', 'bob-profile', '{"id": 1, "name": "Bob Smith", "role": "developer"}', 'application/json', 200, 'Returns user profile data'),
            (2, 'Health Check', 'bob-health', '{"status": "ok", "version": "1.2.3"}', 'application/json', 200, 'Service health endpoint'),
            (2, 'Error Example', 'bob-error', '{"error": "Not Found", "code": 404}', 'application/json', 404, 'Example error response'),
            (3, 'Product List', 'charlie-products', '[{"id": 1, "name": "Widget A"}, {"id": 2, "name": "Widget B"}]', 'application/json', 200, 'Product catalog mock'),
            (3, 'Order Status', 'charlie-order', '{"order_id": "ORD-001", "status": "shipped"}', 'application/json', 200, 'Order tracking mock'),
            (1, 'Admin Config', 'alice-config', '{"maintenance": false, "max_upload_mb": 50}', 'application/json', 200, 'Admin configuration endpoint'),
            (4, 'Weather API', 'diana-weather', '{"temp": 22, "condition": "sunny", "city": "London"}', 'application/json', 200, 'Weather data mock'),
            (4, 'Currency Rates', 'diana-fx', '{"USD": 1.0, "EUR": 0.92, "GBP": 0.79}', 'application/json', 200, 'FX rates mock'),
            (5, 'Login Response', 'eve-login', '{"token": "eyJhbGciOiJIUzI1NiJ9.test", "expires_in": 3600}', 'application/json', 200, 'Auth token mock'),
            (5, 'Plain Text Response', 'eve-text', 'Hello from the API server!', 'text/plain', 200, 'Simple text response'),
        ]
        conn.executemany(
            """INSERT INTO mock_endpoints 
               (user_id, name, slug, response_body, content_type, status_code, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            endpoints
        )

        logs = [
            (1, 2, 'endpoint_created', '127.0.0.1', 'Mozilla/5.0', 'Created bob-profile'),
            (2, 3, 'endpoint_created', '127.0.0.1', 'Mozilla/5.0', 'Created charlie-products'),
            (3, 1, 'endpoint_created', '127.0.0.1', 'Mozilla/5.0', 'Created alice-config'),
            (None, 1, 'login', '10.0.0.1', 'curl/7.81.0', 'Admin login'),
            (None, 2, 'login', '192.168.1.5', 'Mozilla/5.0 Chrome', 'User login'),
        ]
        conn.executemany(
            """INSERT INTO request_logs 
               (endpoint_id, user_id, action, ip_address, user_agent, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            logs
        )

        conn.commit()
        logger.info("Database seeded with initial data")
    except Exception as e:
        logger.error(f"Seed error: {e}")
        conn.rollback()
    finally:
        conn.close()


def log_action(endpoint_id, user_id, action, ip_address, user_agent, details):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO request_logs 
               (endpoint_id, user_id, action, ip_address, user_agent, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (endpoint_id, user_id, action, ip_address, user_agent, details)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Log error: {e}")
    finally:
        conn.close()