import sqlite3
import hashlib
import os

DB_PATH = os.environ.get('DB_PATH', '/data/documind.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    display_name TEXT,
    email TEXT,
    department TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    size_bytes INTEGER DEFAULT 0,
    category TEXT DEFAULT 'general',
    tags TEXT DEFAULT '',
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    doc_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    theme TEXT DEFAULT 'light',
    notifications_enabled INTEGER DEFAULT 1,
    default_category TEXT DEFAULT 'general',
    ai_persona TEXT DEFAULT 'professional',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
'''

SEED_USERS = [
    ('hr_manager',  'password123', 'hr',    'Sarah Mitchell',    'sarah.mitchell@acme.corp',  'Human Resources'),
    ('analyst',     'analyst456',  'user',  'James Okafor',      'james.okafor@acme.corp',    'Finance'),
    ('admin',       'adminpass',   'admin', 'System Admin',      'admin@acme.corp',            'IT'),
    ('recruiter',   'recruit789',  'user',  'Priya Sharma',      'priya.sharma@acme.corp',    'Talent Acquisition'),
    ('legal',       'legal2024',   'user',  'Marcus Webb',       'marcus.webb@acme.corp',     'Legal'),
]

SEED_DOCS = [
    # owner username, filename, content, category
    ('hr_manager', 'Q1_Review_Alice_Johnson.txt',
     'Alice Johnson – Q1 2024 Performance Review\nDepartment: Engineering\nRating: Exceeds Expectations (4.5/5)\n\nKey Achievements:\n- Led migration to new HRIS platform, completed 2 weeks ahead of schedule\n- Reduced employee onboarding time by 30% through process automation\n- Mentored 3 junior developers; all received positive mid-year feedback\n- Delivered $180k in process savings through vendor renegotiation\n\nAreas for Development:\n- Public speaking and executive communication\n- Cross-functional project visibility\n\nRecommendation: Promote to Senior People Analyst by Q3 2024. Salary adjustment to $112,000 recommended.',
     'performance'),

    ('hr_manager', 'Q1_Review_Bob_Martinez.txt',
     'Bob Martinez – Q1 2024 Performance Review\nDepartment: Operations\nRating: Meets Expectations (3.2/5)\n\nKey Achievements:\n- Maintained 99.2% SLA targets across all service desk tickets\n- Completed mandatory compliance and data governance training\n- Contributed to office relocation project coordination\n\nAreas for Development:\n- Initiative and proactive problem-solving\n- Technical skill development in Python/SQL\n\nRecommendation: Standard 3% merit increase. No promotion at this time. Revisit performance trajectory in Q3.',
     'performance'),

    ('hr_manager', 'Q1_Review_Carol_Nguyen.txt',
     'Carol Nguyen – Q1 2024 Performance Review\nDepartment: Sales\nRating: Outstanding (4.9/5)\n\nKey Achievements:\n- Closed 3 enterprise deals totaling $2.1M in new ARR\n- Exceeded quarterly quota by 148%\n- Recruited and onboarded 2 new mid-market account executives\n- Won company-wide "Deal of the Quarter" award for Apex Corp account\n\nAreas for Development:\n- Delegation to junior team members\n\nRecommendation: Bonus of 15% base salary. Promote to Regional Sales Director effective Q2 2024. Base salary increase to $165,000.',
     'performance'),

    ('hr_manager', 'Salary_Data_2024.txt',
     'Confidential salary data: CEO $450k, CTO $380k, VP Sales $310k. Budget: $12.5M headcount.\n\nFull Band Schedule 2024:\nL1 (Junior): $72,000–$88,000\nL2 (Mid): $88,000–$115,000\nL3 (Senior): $115,000–$150,000\nL4 (Staff): $150,000–$195,000\nL5 (Principal): $195,000–$260,000\nDirector: $220,000–$310,000\nVP: $280,000–$380,000\nC-Suite: $350,000–$450,000\n\nBonus pool: $3.2M across 420 employees. Performance-linked distribution to be finalized by CFO by April 30.',
     'compensation'),

    ('hr_manager', 'Headcount_Plan_2024.txt',
     'ACME Corp – 2024 Headcount Plan\nApproved headcount additions by department:\n\nEngineering: +12 (3 senior, 6 mid, 3 junior)\nSales: +8 (2 regional managers, 6 AEs)\nProduct: +4 (1 director, 2 PMs, 1 researcher)\nHR: +2 (1 HRBP, 1 recruiter)\nFinance: +3 (1 controller, 2 analysts)\nLegal: +1 (employment counsel)\n\nTotal new roles: 30\nEstimated annual cost: $4.1M fully loaded\nRecruitment budget: $320,000 (agency + tools)\nTarget start dates: Q2-Q3 2024',
     'planning'),

    ('hr_manager', 'PIP_Template_v3.txt',
     'PERFORMANCE IMPROVEMENT PLAN – Template v3\n\nEmployee Name: [EMPLOYEE]\nManager: [MANAGER]\nHR Business Partner: [HRBP]\nPlan Duration: 90 days\nStart Date: [DATE]\n\nObjective: This plan outlines specific, measurable improvements required to meet role expectations.\n\nPerformance Concerns:\n1. [CONCERN_1]\n2. [CONCERN_2]\n\nSuccess Metrics:\n- [METRIC_1]\n- [METRIC_2]\n\nCheck-in Schedule: Weekly with direct manager, bi-weekly with HRBP\n\nConsequences of Non-Improvement: Up to and including termination of employment.\n\nSignatures: _____________ Employee  _____________ Manager  _____________ HR',
     'templates'),

    ('analyst', 'Finance_Headcount_Request_Q2.txt',
     'Finance Department – Q2 Headcount Request\nSubmitted by: James Okafor, Finance Analyst\nDate: March 15, 2024\n\nRequested Positions:\n1. Senior Financial Controller – Grade L4\n   Justification: Current controller managing 3x recommended workload post-restructuring\n   Estimated comp: $175,000 + benefits\n\n2. FP&A Analyst (x2) – Grade L2\n   Justification: New business units require dedicated financial modeling support\n   Estimated comp: $95,000 each + benefits\n\nTotal annual cost impact: $375,000 fully loaded\nTarget hire date: May 1, 2024\nApproval required from: CFO, HR, Finance Committee',
     'planning'),

    ('recruiter', 'Open_Roles_April_2024.txt',
     'Talent Acquisition – Open Roles Tracker (April 2024)\n\nJOB_ID | TITLE | DEPT | LEVEL | STATUS | RECRUITER\nENG-041 | Senior Backend Engineer | Engineering | L3 | Interview | Priya\nENG-042 | ML Engineer | Engineering | L3 | Screening | Priya\nSAL-019 | Account Executive (West) | Sales | L2 | Offer | Priya\nSAL-020 | Account Executive (East) | Sales | L2 | Interview | Priya\nPRD-011 | Senior Product Manager | Product | L3 | Sourcing | Priya\nHR-007 | HR Business Partner | HR | L2 | Screening | Priya\n\nNotes: SAL-019 offer extended at $98,500 base + $40k OTE. Decision expected by April 12.',
     'recruiting'),

    ('legal', 'NDA_Standard_v2.txt',
     'MUTUAL NON-DISCLOSURE AGREEMENT\nVersion 2.1 – Standard Template\nEffective: January 1, 2024\n\nThis Mutual Non-Disclosure Agreement ("Agreement") is entered into between ACME Corp ("Company") and the counterparty identified in the accompanying Order Form ("Recipient").\n\n1. CONFIDENTIAL INFORMATION: Each party may disclose confidential business, technical, or financial information.\n\n2. OBLIGATIONS: Recipient shall (a) hold information in strict confidence; (b) not disclose to third parties; (c) use only for evaluation purposes.\n\n3. EXCLUSIONS: Obligations do not apply to information that is publicly known, independently developed, or disclosed by court order.\n\n4. TERM: 3 years from effective date.\n\n5. RETURN OF INFORMATION: Upon request, all materials to be returned or destroyed within 10 business days.\n\nGoverning Law: Delaware. Disputes subject to binding arbitration.',
     'legal'),

    ('legal', 'Employment_Contract_Template.txt',
     'EMPLOYMENT AGREEMENT – Standard Template v4\nACME Corp | Legal Department\n\nThis Employment Agreement is between ACME Corp, a Delaware corporation, and [EMPLOYEE_NAME].\n\n1. POSITION: [JOB_TITLE], reporting to [MANAGER_TITLE].\n2. START DATE: [START_DATE]\n3. COMPENSATION: Base salary of $[BASE_SALARY] per year, paid bi-weekly.\n4. BENEFITS: Health, dental, vision (effective day 1). 401(k) with 4% match after 90 days. 20 days PTO.\n5. EQUITY: [EQUITY_GRANT] RSUs vesting over 4 years with 1-year cliff.\n6. AT-WILL: Employment is at-will and may be terminated by either party.\n7. CONFIDENTIALITY: Employee agrees to maintain confidentiality of proprietary information.\n8. NON-COMPETE: 12-month restriction on direct competitors within the United States.\n\nSignatures: _________________________ Employee   _________________________ CEO',
     'legal'),
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA)

    # Seed users
    user_ids = {}
    for username, password, role, display_name, email, department in SEED_USERS:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn.execute(
                'INSERT INTO users (username, password_hash, role, display_name, email, department) VALUES (?, ?, ?, ?, ?, ?)',
                (username, pw_hash, role, display_name, email, department)
            )
        except sqlite3.IntegrityError:
            pass
        row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if row:
            user_ids[username] = row['id']
            # Default settings
            try:
                conn.execute('INSERT INTO user_settings (user_id) VALUES (?)', (row['id'],))
            except sqlite3.IntegrityError:
                pass

    # Seed documents
    for owner_username, filename, content, category in SEED_DOCS:
        uid = user_ids.get(owner_username)
        if uid is None:
            continue
        existing = conn.execute(
            'SELECT id FROM documents WHERE owner_id = ? AND filename = ?', (uid, filename)
        ).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO documents (owner_id, filename, content, size_bytes, category) VALUES (?, ?, ?, ?, ?)',
                (uid, filename, content, len(content), category)
            )

    conn.commit()
    conn.close()