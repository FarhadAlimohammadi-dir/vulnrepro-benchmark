import sqlite3
import bcrypt
import logging
import os
from flask import current_app, g
from flask_login import UserMixin

logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, username, email, role, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash)

    def is_admin(self):
        return self.role == 'admin'


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(app):
    db_path = app.config['DATABASE_PATH']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            template_name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS report_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            shared_with INTEGER NOT NULL,
            permission TEXT DEFAULT 'view',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (shared_with) REFERENCES users(id)
        );
    ''')

    # Seed users
    users = [
        ('alice', 'alice@reportforge.io', 'AlicePass123!', 'user'),
        ('bob', 'bob@reportforge.io', 'BobPass123!', 'user'),
        ('charlie', 'charlie@reportforge.io', 'CharliePass123!', 'admin'),
        ('diana', 'diana@reportforge.io', 'DianaPass456!', 'user'),
        ('eve', 'eve@reportforge.io', 'EvePass789!', 'user'),
    ]

    for username, email, password, role in users:
        existing = cur.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cur.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (username, email, pw_hash, role)
            )

    conn.commit()

    # Seed reports
    alice_id = cur.execute('SELECT id FROM users WHERE username = ?', ('alice',)).fetchone()['id']
    bob_id = cur.execute('SELECT id FROM users WHERE username = ?', ('bob',)).fetchone()['id']
    charlie_id = cur.execute('SELECT id FROM users WHERE username = ?', ('charlie',)).fetchone()['id']

    sample_reports = [
        ('Q1 2024 Sales Report', 'Quarterly sales performance analysis', 'quarterly_sales.txt', alice_id, 'published'),
        ('Customer Churn Analysis', 'Monthly churn metrics and cohort analysis', 'churn_analysis.txt', alice_id, 'draft'),
        ('Marketing Campaign ROI', 'Campaign effectiveness metrics for Q1', 'marketing_roi.txt', bob_id, 'published'),
        ('Product Performance Dashboard', 'SKU-level performance breakdown', 'product_perf.txt', bob_id, 'draft'),
        ('Infrastructure Cost Report', 'Cloud spend analysis and projections', 'infra_costs.txt', charlie_id, 'published'),
        ('HR Headcount Report', 'Department-level headcount and attrition', 'hr_headcount.txt', charlie_id, 'draft'),
        ('Revenue Forecast Q2', 'Predictive revenue model for Q2 2024', 'revenue_forecast.txt', alice_id, 'published'),
        ('Support Ticket Trends', 'Issue category breakdown and SLA metrics', 'support_trends.txt', bob_id, 'published'),
        ('Inventory Turnover Analysis', 'Warehouse efficiency and stock levels', 'inventory.txt', alice_id, 'draft'),
        ('Compliance Audit Summary', 'Regulatory compliance status across BUs', 'compliance.txt', charlie_id, 'published'),
        ('Partner Revenue Share', 'Channel partner contribution analysis', 'partner_revenue.txt', bob_id, 'draft'),
        ('Executive KPI Snapshot', 'Top-level KPIs for board presentation', 'exec_kpi.txt', charlie_id, 'published'),
    ]

    for title, desc, tmpl, owner, status in sample_reports:
        existing = cur.execute('SELECT id FROM reports WHERE title = ?', (title,)).fetchone()
        if not existing:
            cur.execute(
                'INSERT INTO reports (title, description, template_name, owner_id, status) VALUES (?, ?, ?, ?, ?)',
                (title, desc, tmpl, owner, status)
            )

    conn.commit()
    conn.close()

    # Create report template files
    template_dir = app.config['TEMPLATE_DIR']
    os.makedirs(template_dir, exist_ok=True)

    templates = {
        'quarterly_sales.txt': 'QUARTERLY SALES REPORT\n======================\nRevenue: $4.2M\nGrowth: 12% YoY\nTop Region: Northeast\n',
        'churn_analysis.txt': 'CUSTOMER CHURN ANALYSIS\n=======================\nChurn Rate: 3.2%\nAt-Risk Accounts: 142\nRetention Actions: 87\n',
        'marketing_roi.txt': 'MARKETING ROI REPORT\n====================\nCampaign Spend: $280K\nAttributed Revenue: $1.1M\nROI: 293%\n',
        'product_perf.txt': 'PRODUCT PERFORMANCE\n===================\nTop SKU: RF-2041\nUnits Sold: 14,320\nReturns: 2.1%\n',
        'infra_costs.txt': 'INFRASTRUCTURE COSTS\n====================\nTotal Spend: $42,000/mo\nCompute: 68%\nStorage: 22%\nNetwork: 10%\n',
        'hr_headcount.txt': 'HR HEADCOUNT REPORT\n===================\nTotal FTEs: 312\nOpen Reqs: 28\nAttrition: 8.4%\n',
        'revenue_forecast.txt': 'REVENUE FORECAST Q2\n===================\nProjected: $5.1M\nConfidence: 87%\nKey Driver: Enterprise segment\n',
        'support_trends.txt': 'SUPPORT TICKET TRENDS\n=====================\nTotal Tickets: 2,841\nAvg Resolution: 4.2h\nEscalations: 3.1%\n',
        'inventory.txt': 'INVENTORY ANALYSIS\n==================\nTurnover Rate: 6.2x\nDead Stock: $18K\nReorder Alerts: 23\n',
        'compliance.txt': 'COMPLIANCE SUMMARY\n==================\nSOC2: Compliant\nGDPR: Compliant\nOpen Findings: 4\n',
        'partner_revenue.txt': 'PARTNER REVENUE SHARE\n=====================\nChannel Revenue: $890K\nTop Partner: Acme Corp\nCommission Paid: $89K\n',
        'exec_kpi.txt': 'EXECUTIVE KPI SNAPSHOT\n======================\nARR: $18.4M\nNPS: 62\nBurn Multiple: 1.4\n',
        'default.txt': 'REPORT TEMPLATE\n===============\nThis is a default report template.\nCustomize as needed.\n',
    }

    for fname, content in templates.items():
        fpath = os.path.join(template_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, 'w') as f:
                f.write(content)

    logger.info("Database and templates initialized successfully")