import sqlite3
import hashlib
import bcrypt
import logging
import os

logger = logging.getLogger(__name__)


def get_db(app):
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(app):
    conn = get_db(app)
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            department TEXT,
            employee_id TEXT UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'medium',
            created_by INTEGER,
            assigned_to INTEGER,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT,
            author_id INTEGER,
            published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            requested_resource TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    conn.commit()
    conn.close()
    logger.info("Database schema initialized")


def seed_db(app):
    conn = get_db(app)
    cursor = conn.cursor()

    existing = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    logger.info("Seeding database with initial data")

    users = [
        ('admin', 'admin@helpdesk.internal', 'AdminSecure#9912', 'admin', 'IT', 'EMP001'),
        ('alice', 'alice@helpdesk.internal', 'AlicePass123!', 'user', 'Engineering', 'EMP002'),
        ('bob', 'bob@helpdesk.internal', 'BobPass123!', 'user', 'Marketing', 'EMP003'),
        ('charlie', 'charlie@helpdesk.internal', 'CharliePass123!', 'user', 'Finance', 'EMP004'),
        ('diana', 'diana@helpdesk.internal', 'DianaPass456!', 'user', 'HR', 'EMP005'),
        ('evan', 'evan@helpdesk.internal', 'EvanPass789!', 'user', 'Sales', 'EMP006'),
        ('fiona', 'fiona@helpdesk.internal', 'FionaPass321!', 'manager', 'Engineering', 'EMP007'),
        ('george', 'george@helpdesk.internal', 'GeorgePass654!', 'user', 'Operations', 'EMP008'),
    ]

    for username, email, password, role, dept, emp_id in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, email, password_hash, role, department, employee_id) VALUES (?,?,?,?,?,?)",
            (username, email, pw_hash, role, dept, emp_id)
        )

    tickets = [
        ('Cannot access VPN', 'VPN client throws error 619 on Windows 11', 'open', 'high', 2, 1, 'Network'),
        ('Email not syncing', 'Outlook not syncing since Monday morning', 'in_progress', 'medium', 3, 7, 'Email'),
        ('New laptop setup request', 'Need MacBook Pro provisioned for new hire', 'open', 'low', 7, 1, 'Hardware'),
        ('Password reset needed', 'Locked out of internal wiki after too many attempts', 'resolved', 'medium', 4, 1, 'Access'),
        ('Printer offline in Room 204', 'HP LaserJet shows offline, rebooting didnt help', 'open', 'low', 5, 8, 'Hardware'),
        ('Slack workspace missing channels', 'Several channels disappeared after workspace migration', 'in_progress', 'medium', 6, 7, 'Collaboration'),
        ('Software license renewal', 'Adobe CC licenses expire end of month', 'open', 'high', 7, 1, 'Software'),
        ('Database slow queries alert', 'Production DB reporting avg query time > 2s', 'open', 'critical', 2, 1, 'Database'),
        ('Office 365 MFA issue', 'MFA prompts every hour instead of every 30 days', 'resolved', 'medium', 3, 7, 'Access'),
        ('WiFi dead zones on floor 3', 'Signal drops in conference rooms B and C', 'open', 'medium', 4, 8, 'Network'),
        ('Zoom rooms not working', 'Room A and B Zoom appliances offline after update', 'in_progress', 'high', 5, 7, 'AV'),
        ('Backup job failed overnight', 'Backup for file server FS-02 failed with error 0x800', 'open', 'critical', 1, 1, 'Backup'),
        ('New user onboarding - Diana', 'Setup accounts for HR new hire starting Monday', 'resolved', 'medium', 1, 7, 'Onboarding'),
        ('SSL cert expiry warning', 'helpdesk.internal cert expires in 14 days', 'open', 'high', 1, 1, 'Security'),
        ('Mobile device management', 'Android phones not enrolling in MDM after update', 'open', 'medium', 6, 8, 'Mobile'),
    ]

    for title, desc, status, priority, created_by, assigned_to, category in tickets:
        cursor.execute(
            "INSERT INTO tickets (title, description, status, priority, created_by, assigned_to, category) VALUES (?,?,?,?,?,?,?)",
            (title, desc, status, priority, created_by, assigned_to, category)
        )

    announcements = [
        ('Scheduled Maintenance Window', 'Systems will be down Saturday 02:00-04:00 UTC for patching.', 1, 1),
        ('New Ticketing Workflow', 'All critical tickets now require manager approval before escalation.', 1, 1),
        ('Holiday Support Hours', 'Reduced support coverage Dec 24 - Jan 2. Emergency line remains active.', 7, 1),
        ('VPN Client Update Required', 'Please update GlobalProtect to v6.2 by end of week.', 1, 1),
    ]

    for title, body, author_id, published in announcements:
        cursor.execute(
            "INSERT INTO announcements (title, body, author_id, published) VALUES (?,?,?,?)",
            (title, body, author_id, published)
        )

    audit_entries = [
        (1, 'LOGIN', 'auth', 'Admin logged in', '10.0.0.1'),
        (2, 'TICKET_CREATE', 'tickets', 'Created ticket #1', '10.0.0.2'),
        (3, 'TICKET_UPDATE', 'tickets', 'Updated ticket #2 status', '10.0.0.3'),
        (7, 'USER_UPDATE', 'users', 'Updated department field', '10.0.0.4'),
        (1, 'ANNOUNCEMENT_PUBLISH', 'announcements', 'Published maintenance notice', '10.0.0.1'),
    ]

    for user_id, action, resource, details, ip in audit_entries:
        cursor.execute(
            "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
            (user_id, action, resource, details, ip)
        )

    conn.commit()
    conn.close()
    logger.info("Database seeding complete")