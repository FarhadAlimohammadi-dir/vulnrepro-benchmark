import sqlite3
import os
from flask import current_app
from flask_login import UserMixin


def get_db():
    db_path = current_app.config["DATABASE"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_init(db_path=None):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "data", "forge.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numeric_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            region TEXT NOT NULL DEFAULT 'us-east1',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS storage_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bucket_objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_id INTEGER NOT NULL REFERENCES storage_buckets(id),
            object_key TEXT NOT NULL,
            content TEXT NOT NULL,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            region TEXT NOT NULL DEFAULT 'us-east1',
            runtime TEXT NOT NULL DEFAULT 'python39',
            status TEXT NOT NULL DEFAULT 'DEPLOYING',
            source_bucket TEXT,
            source_object TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS function_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_id INTEGER NOT NULL REFERENCES functions(id),
            message TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'INFO',
            logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS env_vars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_id INTEGER NOT NULL REFERENCES functions(id),
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(function_id, key)
        );
    """)
    conn.commit()
    conn.close()


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.created_at = row["created_at"]

    def get_id(self):
        return str(self.id)


def get_user_by_id(user_id):
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "data", "forge.db")
    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row)
    return None


def get_user_by_username(username):
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "data", "forge.db")
    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row:
        return User(row)
    return None