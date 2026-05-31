import sqlite3
import hashlib
import os
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/nexus.db')


class User(UserMixin):
    def __init__(self, id, username, email, role, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash

    def check_password(self, password):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return hashed == self.password_hash

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()


def get_db():
    db_path = os.environ.get('DATABASE_PATH', DATABASE_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, role, password_hash FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
        return None
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, role, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
        return None
    finally:
        conn.close()


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'analyst',
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            row_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            dataset_id INTEGER,
            template_name TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id),
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            detail TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS report_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            is_shared INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_report_templates_owner_filename
        ON report_templates(owner_id, filename);
    """)

    # Seed users
    users = [
        ('alice', 'alice@nexus-corp.io', 'admin', User.hash_password('AlicePass123!')),
        ('bob', 'bob@nexus-corp.io', 'analyst', User.hash_password('BobPass123!')),
        ('charlie', 'charlie@nexus-corp.io', 'analyst', User.hash_password('CharliePass123!')),
        ('diana', 'diana@nexus-corp.io', 'viewer', User.hash_password('DianaPass456!')),
        ('evan', 'evan@nexus-corp.io', 'analyst', User.hash_password('EvanPass789!')),
    ]

    for username, email, role, pw_hash in users:
        try:
            conn.execute(
                "INSERT INTO users (username, email, role, password_hash) VALUES (?, ?, ?, ?)",
                (username, email, role, pw_hash)
            )
        except sqlite3.IntegrityError:
            pass

    # Seed datasets
    datasets = [
        (1, 'Q1 Sales Data', 'Quarterly sales figures for North America', 4200),
        (1, 'Customer Churn Analysis', 'Monthly churn rates by segment', 15300),
        (2, 'Marketing Campaign ROI', 'Email and paid campaigns performance', 890),
        (2, 'Web Traffic Analytics', 'Daily sessions, bounce rate, conversions', 62000),
        (3, 'Inventory Levels', 'Real-time warehouse stock data', 1100),
        (3, 'Support Ticket Trends', 'Volume and resolution times by category', 7800),
        (1, 'Employee Performance', 'HR metrics and KPIs', 340),
        (2, 'Financial Forecast 2024', 'Revenue and cost projections', 200),
    ]

    for owner_id, name, desc, row_count in datasets:
        try:
            conn.execute(
                "INSERT INTO datasets (name, description, owner_id, row_count) VALUES (?, ?, ?, ?)",
                (name, desc, owner_id, row_count)
            )
        except Exception:
            pass

    # Seed reports
    reports_data = [
        ('Q1 Revenue Summary', 'Executive summary of Q1 performance', 1, 1, 'published'),
        ('Churn Dashboard', 'Interactive churn analysis dashboard', 2, 2, 'published'),
        ('Campaign Performance', 'Marketing effectiveness report', 3, 3, 'draft'),
        ('Traffic Overview', 'Web analytics deep-dive', 4, 2, 'published'),
        ('Inventory Alert Report', 'Low stock notifications', 5, 3, 'draft'),
        ('Ticket Volume Trends', 'Support load over time', 6, 1, 'published'),
        ('HR Quarterly Review', 'People metrics summary', 7, 1, 'draft'),
        ('2024 Financial Outlook', 'Forward-looking projections', 8, 1, 'published'),
        ('NPS Score Analysis', 'Net Promoter Score breakdown', 1, 2, 'draft'),
        ('Product Adoption Funnel', 'Feature adoption by cohort', 3, 3, 'published'),
    ]

    for title, desc, ds_id, owner_id, status in reports_data:
        try:
            conn.execute(
                "INSERT INTO reports (title, description, dataset_id, owner_id, status) VALUES (?, ?, ?, ?, ?)",
                (title, desc, ds_id, owner_id, status)
            )
        except Exception:
            pass

    # Seed audit logs
    audit_entries = [
        (1, 'login', 'session', 'User authenticated successfully', '10.0.1.5'),
        (2, 'login', 'session', 'User authenticated successfully', '10.0.1.12'),
        (1, 'view', 'report:1', 'Viewed Q1 Revenue Summary', '10.0.1.5'),
        (3, 'login', 'session', 'User authenticated successfully', '10.0.2.8'),
        (2, 'create', 'report:9', 'Created NPS Score Analysis', '10.0.1.12'),
        (1, 'export', 'report:2', 'Exported Churn Dashboard as PDF', '10.0.1.5'),
        (3, 'view', 'dataset:5', 'Accessed Inventory Levels dataset', '10.0.2.8'),
        (2, 'update', 'report:3', 'Updated Campaign Performance status', '10.0.1.12'),
        (1, 'admin', 'users', 'Listed all users', '10.0.1.5'),
        (4, 'login', 'session', 'User authenticated successfully', '10.0.3.1'),
    ]

    for user_id, action, resource, detail, ip in audit_entries:
        try:
            conn.execute(
                "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
                (user_id, action, resource, detail, ip)
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    logger.info("Database initialized with seed data")
