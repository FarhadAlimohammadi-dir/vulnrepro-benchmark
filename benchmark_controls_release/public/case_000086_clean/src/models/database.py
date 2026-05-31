import sqlite3
import os
import hashlib
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, id, username, email, role, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash

    def is_admin(self):
        return self.role == 'admin'


def get_db_path():
    return os.environ.get('DATABASE_PATH', '/app/data/docmanager.db')


def get_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    salt = "docmanager_salt_v1"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT id, username, email, role, password_hash FROM users WHERE id = ?',
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
            'SELECT id, username, email, role, password_hash FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
        return None
    finally:
        conn.close()


def init_db(app):
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            category TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            file_size INTEGER DEFAULT 0,
            mime_type TEXT DEFAULT 'application/octet-stream',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_file TEXT NOT NULL,
            description TEXT,
            created_by INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            file_path TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()

    _seed_data(conn, app)
    conn.close()

    _create_report_files(app)
    logger.info("Database initialized successfully")


def _seed_data(conn, app):
    users = [
        ('alice', 'alice@docmanager.io', 'user', hash_password('AlicePass123!')),
        ('bob', 'bob@docmanager.io', 'user', hash_password('BobPass123!')),
        ('charlie', 'charlie@docmanager.io', 'admin', hash_password('CharliePass123!')),
        ('diana', 'diana@docmanager.io', 'user', hash_password('Diana2024!')),
        ('evan', 'evan@docmanager.io', 'manager', hash_password('EvanMgr99!')),
    ]

    for username, email, role, pw_hash in users:
        conn.execute(
            'INSERT OR IGNORE INTO users (username, email, role, password_hash) VALUES (?, ?, ?, ?)',
            (username, email, role, pw_hash)
        )

    conn.commit()

    alice_id = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
    bob_id = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()[0]
    charlie_id = conn.execute("SELECT id FROM users WHERE username='charlie'").fetchone()[0]
    evan_id = conn.execute("SELECT id FROM users WHERE username='evan'").fetchone()[0]

    documents = [
        ('Q1 Financial Summary', 'q1_financial_summary.pdf', 'Finance', alice_id, 204800, 'application/pdf'),
        ('Employee Handbook 2024', 'employee_handbook_2024.pdf', 'HR', charlie_id, 512000, 'application/pdf'),
        ('IT Security Policy', 'it_security_policy.docx', 'IT', charlie_id, 102400, 'application/vnd.openxmlformats'),
        ('Project Alpha Proposal', 'project_alpha_proposal.pdf', 'Projects', bob_id, 307200, 'application/pdf'),
        ('Marketing Strategy Q2', 'marketing_q2_strategy.pptx', 'Marketing', evan_id, 409600, 'application/vnd.openxmlformats'),
        ('Budget Forecast 2024', 'budget_forecast_2024.xlsx', 'Finance', alice_id, 153600, 'application/vnd.openxmlformats'),
        ('Vendor Contracts Index', 'vendor_contracts_index.pdf', 'Legal', charlie_id, 256000, 'application/pdf'),
        ('Customer Onboarding Guide', 'customer_onboarding.pdf', 'Sales', bob_id, 184320, 'application/pdf'),
        ('System Architecture v3', 'system_arch_v3.pdf', 'IT', evan_id, 614400, 'application/pdf'),
        ('Annual Report 2023', 'annual_report_2023.pdf', 'Finance', charlie_id, 1048576, 'application/pdf'),
        ('Meeting Notes - Board Dec 2023', 'board_meeting_dec2023.docx', 'Executive', charlie_id, 81920, 'application/vnd.openxmlformats'),
        ('Data Retention Policy', 'data_retention_policy.pdf', 'Legal', charlie_id, 98304, 'application/pdf'),
    ]

    for title, filename, category, owner_id, size, mime in documents:
        conn.execute(
            'INSERT OR IGNORE INTO documents (title, filename, category, owner_id, file_size, mime_type) VALUES (?, ?, ?, ?, ?, ?)',
            (title, filename, category, owner_id, size, mime)
        )

    reports_data = [
        ('Monthly Revenue Report', 'revenue_monthly.html', 'Tracks monthly revenue by department', alice_id),
        ('User Activity Summary', 'user_activity.html', 'Summary of user actions in the system', charlie_id),
        ('Inventory Status', 'inventory_status.html', 'Current inventory levels across warehouses', evan_id),
        ('Support Ticket Metrics', 'support_metrics.html', 'Help desk performance indicators', bob_id),
        ('Compliance Audit Report', 'compliance_audit.html', 'Quarterly compliance tracking', charlie_id),
    ]

    for name, template, desc, creator in reports_data:
        conn.execute(
            'INSERT OR IGNORE INTO reports (name, template_file, description, created_by) VALUES (?, ?, ?, ?)',
            (name, template, desc, creator)
        )

    audit_entries = [
        (alice_id, 'LOGIN', 'auth', '192.168.1.10', 'Successful login'),
        (bob_id, 'VIEW_DOCUMENT', 'documents/4', '192.168.1.22', 'Viewed Project Alpha Proposal'),
        (charlie_id, 'CREATE_TEMPLATE', 'templates', '192.168.1.1', 'Created new report template'),
        (evan_id, 'DOWNLOAD', 'documents/5', '192.168.1.50', 'Downloaded Marketing Strategy Q2'),
        (alice_id, 'VIEW_REPORT', 'reports/1', '192.168.1.10', 'Previewed Monthly Revenue Report'),
        (charlie_id, 'USER_CREATED', 'users', '192.168.1.1', 'Created user diana'),
        (bob_id, 'UPLOAD', 'documents', '192.168.1.22', 'Uploaded new document'),
        (evan_id, 'LOGIN', 'auth', '192.168.1.50', 'Successful login'),
        (alice_id, 'LOGOUT', 'auth', '192.168.1.10', 'User logged out'),
        (charlie_id, 'CONFIG_CHANGE', 'admin', '192.168.1.1', 'Updated system configuration'),
    ]

    for user_id, action, resource, ip, details in audit_entries:
        conn.execute(
            'INSERT OR IGNORE INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
            (user_id, action, resource, ip, details)
        )

    templates_data = [
        ('Standard Report', 'Default template for standard reports', 'standard_report.html', charlie_id),
        ('Executive Summary', 'One-page executive summary layout', 'exec_summary.html', charlie_id),
        ('Detailed Audit', 'Full audit trail template', 'detailed_audit.html', charlie_id),
    ]

    for name, desc, file_path, creator in templates_data:
        conn.execute(
            'INSERT OR IGNORE INTO templates (name, description, file_path, created_by) VALUES (?, ?, ?, ?)',
            (name, desc, file_path, creator)
        )

    conn.commit()


def _create_report_files(app):
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    report_files = {
        'revenue_monthly.html': '''<html><body>
<h1>Monthly Revenue Report</h1>
<table>
<tr><th>Department</th><th>Revenue</th></tr>
<tr><td>Sales</td><td>$1,240,000</td></tr>
<tr><td>Services</td><td>$380,000</td></tr>
<tr><td>Subscriptions</td><td>$560,000</td></tr>
</table>
</body></html>''',
        'user_activity.html': '''<html><body>
<h1>User Activity Summary</h1>
<p>Total logins this month: 1,842</p>
<p>Documents accessed: 5,623</p>
<p>Reports generated: 312</p>
</body></html>''',
        'inventory_status.html': '''<html><body>
<h1>Inventory Status</h1>
<p>Items in stock: 14,230</p>
<p>Low stock alerts: 23</p>
<p>Pending orders: 157</p>
</body></html>''',
        'support_metrics.html': '''<html><body>
<h1>Support Ticket Metrics</h1>
<p>Open tickets: 84</p>
<p>Resolved this week: 213</p>
<p>Average resolution time: 4.2 hours</p>
</body></html>''',
        'compliance_audit.html': '''<html><body>
<h1>Compliance Audit Report</h1>
<p>Controls assessed: 147</p>
<p>Passed: 139</p>
<p>Exceptions noted: 8</p>
</body></html>''',
    }

    for filename, content in report_files.items():
        filepath = os.path.join(reports_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content)