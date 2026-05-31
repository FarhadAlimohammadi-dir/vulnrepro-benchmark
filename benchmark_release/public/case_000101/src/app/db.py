import sqlite3
from datetime import datetime


def init_db(db_path: str):
    """
    Initialize SQLite database with required schema.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Builds cache table
    c.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            result TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # Audit log table for compliance and operations review
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on cache_key for fast lookups
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_builds_cache_key ON builds(cache_key)
    """)

    # TODO: add package_blacklist table for policy enforcement
    # TODO: add device_profiles table for hardware variant metadata
    # TODO: partition audit_log by month for archival — expected volume ~10k rows/day

    conn.commit()
    conn.close()


def get_user(db_path: str, username: str):
    """
    Retrieve user record by username.
    Returns tuple (user_id, username, password) or None if not found.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT user_id, username, password FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row