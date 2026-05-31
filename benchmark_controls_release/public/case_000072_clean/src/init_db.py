import sqlite3
import os
import bcrypt
import json
from datetime import datetime, timedelta
import random

DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/docuvault.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.executescript('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    detected_mime TEXT,
    file_size INTEGER,
    status TEXT DEFAULT 'pending',
    processed_content TEXT,
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    shared_by INTEGER NOT NULL,
    shared_with INTEGER NOT NULL,
    permission TEXT DEFAULT 'read',
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
''')

def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

now = datetime.utcnow()

users = [
    ('alice', 'alice@docuvault.io', hash_password('AlicePass123!'), 'admin'),
    ('bob', 'bob@docuvault.io', hash_password('BobPass123!'), 'user'),
    ('charlie', 'charlie@docuvault.io', hash_password('CharliePass123!'), 'user'),
    ('diana', 'diana@docuvault.io', hash_password('Diana2024#'), 'user'),
    ('eve', 'eve@docuvault.io', hash_password('Eve$ecure99'), 'user'),
]

for u in users:
    try:
        c.execute(
            'INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?,?,?,?,?)',
            (u[0], u[1], u[2], u[3], now.isoformat())
        )
    except sqlite3.IntegrityError:
        pass

conn.commit()

c.execute('SELECT id FROM users WHERE username=?', ('alice',))
alice_id = c.fetchone()[0]
c.execute('SELECT id FROM users WHERE username=?', ('bob',))
bob_id = c.fetchone()[0]
c.execute('SELECT id FROM users WHERE username=?', ('charlie',))
charlie_id = c.fetchone()[0]

sample_docs = [
    (alice_id, 'doc_001.pdf', 'Q3_Financial_Report.pdf', 'application/pdf', 245678, 'processed',
     'Q3 revenue: $4.2M. Operating expenses down 12%. EBITDA margin improved to 23%.'),
    (alice_id, 'doc_002.pdf', 'Annual_Compliance_Review.pdf', 'application/pdf', 189234, 'processed',
     'All 47 compliance checkpoints passed. Two minor findings resolved. Next review: Q1 2025.'),
    (alice_id, 'doc_003.json', 'pipeline_config.json', 'application/json', 3421, 'stored',
     None),
    (bob_id, 'doc_004.pdf', 'Project_Proposal_v2.pdf', 'application/pdf', 512890, 'processed',
     'Project Alpha: 18-month timeline. Budget request $850K. Team of 12 engineers.'),
    (bob_id, 'doc_005.json', 'api_schema_v3.json', 'application/json', 8932, 'stored',
     None),
    (bob_id, 'doc_006.pdf', 'Vendor_Contract_2024.pdf', 'application/pdf', 334512, 'processed',
     'Service agreement with TechVendor Inc. Term: 2 years. SLA: 99.9% uptime.'),
    (charlie_id, 'doc_007.pdf', 'Marketing_Deck_Q4.pdf', 'application/pdf', 1234567, 'processed',
     'Q4 campaign targets: 40% increase in enterprise leads. Budget allocation: $200K.'),
    (charlie_id, 'doc_008.json', 'feature_flags.json', 'application/json', 2341, 'stored',
     None),
    (alice_id, 'doc_009.pdf', 'Board_Meeting_Minutes.pdf', 'application/pdf', 98765, 'processed',
     'Agenda: Q3 results, headcount planning, product roadmap. Next meeting: Nov 15.'),
    (bob_id, 'doc_010.pdf', 'Technical_Architecture.pdf', 'application/pdf', 678234, 'processed',
     'Microservices migration plan. Phase 1: Auth service. Phase 2: Data pipeline.'),
    (charlie_id, 'doc_011.json', 'notification_rules.json', 'application/json', 4521, 'stored',
     None),
    (alice_id, 'doc_012.pdf', 'HR_Policy_Update.pdf', 'application/pdf', 156789, 'processed',
     'Remote work policy updated. Flex hours: 7am-7pm core overlap. Quarterly reviews.'),
]

for d in sample_docs:
    ts = (now - timedelta(days=random.randint(1, 90))).isoformat()
    try:
        c.execute(
            '''INSERT INTO documents 
               (owner_id, filename, original_name, detected_mime, file_size, status, processed_content, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (d[0], d[1], d[2], d[3], d[4], d[5], d[6], ts, ts)
        )
    except Exception:
        pass

audit_actions = [
    (alice_id, 'user.login', 'user', alice_id, '{"ip": "10.0.0.1"}'),
    (bob_id, 'document.upload', 'document', 4, '{"filename": "Project_Proposal_v2.pdf"}'),
    (alice_id, 'document.view', 'document', 1, '{"filename": "Q3_Financial_Report.pdf"}'),
    (charlie_id, 'user.login', 'user', charlie_id, '{"ip": "10.0.0.5"}'),
    (bob_id, 'document.share', 'document', 4, '{"shared_with": "charlie"}'),
    (alice_id, 'admin.audit_view', 'audit', None, '{"filters": "last_7_days"}'),
    (alice_id, 'document.upload', 'document', 9, '{"filename": "Board_Meeting_Minutes.pdf"}'),
    (bob_id, 'document.search', None, None, '{"query": "contract 2024"}'),
]

for a in audit_actions:
    ts = (now - timedelta(hours=random.randint(1, 168))).isoformat()
    c.execute(
        'INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, created_at) VALUES (?,?,?,?,?,?,?)',
        (a[0], a[1], a[2], a[3], a[4], '127.0.0.1', ts)
    )

conn.commit()
conn.close()
print("Database initialized successfully.")