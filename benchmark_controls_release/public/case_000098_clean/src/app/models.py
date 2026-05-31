import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def get_db(db_path=None):
    if db_path is None:
        db_path = os.environ.get('DATABASE_PATH', '/app/data/relay.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS relay_endpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            target_url TEXT NOT NULL,
            method TEXT DEFAULT 'POST',
            headers TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relay_id INTEGER NOT NULL,
            payload TEXT,
            status_code INTEGER,
            response_body TEXT,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_ms INTEGER,
            success INTEGER DEFAULT 0,
            FOREIGN KEY (relay_id) REFERENCES relay_endpoints(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS webhook_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relay_id INTEGER NOT NULL UNIQUE,
            secret_hash TEXT NOT NULL,
            algorithm TEXT DEFAULT 'hmac-sha256',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (relay_id) REFERENCES relay_endpoints(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", db_path)