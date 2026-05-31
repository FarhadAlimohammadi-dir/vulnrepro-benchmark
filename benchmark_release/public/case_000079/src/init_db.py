import sqlite3
import bcrypt
import os
import json

DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            department TEXT,
            api_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            secret TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
    ''')

    users = [
        ('alice', 'alice@corp.example.com', 'AlicePass123!', 'user', 'Engineering', 'ak_alice_7f3d9a'),
        ('bob', 'bob@corp.example.com', 'BobPass123!', 'user', 'Marketing', 'ak_bob_2c8e1b'),
        ('charlie', 'charlie@corp.example.com', 'CharliePass123!', 'admin', 'IT', 'ak_charlie_9x4p2q'),
        ('diana', 'diana@corp.example.com', 'Diana$ecure99', 'user', 'Finance', 'ak_diana_5r7m3n'),
        ('evan', 'evan@corp.example.com', 'Ev@n2024!', 'user', 'Engineering', 'ak_evan_1k9j4h'),
        ('fiona', 'fiona@corp.example.com', 'Fi0na#Pass', 'manager', 'HR', 'ak_fiona_8p2w6s'),
        ('george', 'george@corp.example.com', 'G30rge!2024', 'user', 'Sales', 'ak_george_3v5n8l'),
        ('helen', 'helen@corp.example.com', 'H3len@Corp', 'user', 'Engineering', 'ak_helen_6t1r9k'),
        ('ivan', 'ivan@corp.example.com', 'Iv@n!Secure', 'user', 'DevOps', 'ak_ivan_4m7c2x'),
        ('julia', 'julia@corp.example.com', 'Jul!a2024#', 'manager', 'Finance', 'ak_julia_9q8y1z'),
    ]

    for username, email, password, role, dept, api_key in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            cur.execute(
                'INSERT INTO users (username, email, password_hash, role, department, api_key) VALUES (?,?,?,?,?,?)',
                (username, email, pw_hash, role, dept, api_key)
            )
        except sqlite3.IntegrityError:
            pass

    reports_data = [
        (1, 'Q1 Engineering Review', 'Engineering performance and deliverables for Q1 2024', 'published'),
        (3, 'Security Audit 2024', 'Annual security posture assessment', 'published'),
        (2, 'Marketing Campaign Analysis', 'ROI analysis for H1 campaigns', 'draft'),
        (6, 'HR Policy Updates', 'New remote work policy guidelines', 'published'),
        (4, 'Financial Projections Q3', 'Revenue forecasting model', 'draft'),
        (5, 'Infrastructure Upgrade Plan', 'Cloud migration roadmap', 'published'),
        (7, 'Sales Pipeline Review', 'CRM data analysis and conversion rates', 'published'),
        (1, 'API Gateway Performance', 'Latency and throughput benchmarks', 'published'),
        (9, 'DevOps Incident Report', 'Post-mortem for the March 15 outage', 'published'),
        (10, 'Budget Allocation FY2025', 'Department budget proposals', 'draft'),
    ]

    for author_id, title, content, status in reports_data:
        try:
            cur.execute(
                'INSERT INTO reports (title, author_id, content, status) VALUES (?,?,?,?)',
                (title, author_id, content, status)
            )
        except Exception:
            pass

    audit_entries = [
        (1, 'LOGIN', 'auth', 'User logged in', '10.0.1.5'),
        (3, 'CREATE_REPORT', 'reports', 'Created security audit report', '10.0.1.1'),
        (1, 'UPDATE_PROFILE', 'users', 'Updated email preference', '10.0.1.5'),
        (2, 'LOGIN', 'auth', 'User logged in', '192.168.1.20'),
        (3, 'LIST_USERS', 'users', 'Admin viewed user list', '10.0.1.1'),
        (6, 'CREATE_WEBHOOK', 'webhooks', 'Created HR notification webhook', '10.0.1.8'),
        (3, 'DELETE_USER', 'users', 'Deactivated test account', '10.0.1.1'),
        (4, 'VIEW_REPORT', 'reports', 'Viewed Q3 financial projections', '10.0.2.15'),
        (1, 'API_CALL', 'grpc', 'Internal service sync', '127.0.0.1'),
        (3, 'ADMIN_ACTION', 'users', 'Reset API keys', '10.0.1.1'),
    ]

    for user_id, action, resource, details, ip in audit_entries:
        try:
            cur.execute(
                'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
                (user_id, action, resource, details, ip)
            )
        except Exception:
            pass

    webhooks_data = [
        ('HR Notifications', 'https://hooks.internal.corp/hr', 'whs_abc123xyz', 1, 6),
        ('Deploy Alerts', 'https://hooks.internal.corp/deploy', 'whs_def456uvw', 1, 9),
        ('Finance Reports', 'https://hooks.internal.corp/finance', 'whs_ghi789rst', 0, 10),
    ]

    for name, url, secret, active, created_by in webhooks_data:
        try:
            cur.execute(
                'INSERT INTO webhooks (name, url, secret, active, created_by) VALUES (?,?,?,?,?)',
                (name, url, secret, active, created_by)
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    print(f"[init_db] Database initialized at {DB_PATH}")

if __name__ == '__main__':
    init()