import sqlite3
import bcrypt
import secrets
import logging
import os
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path):
    global DB_PATH
    DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            plan TEXT DEFAULT 'free',
            created_at TEXT NOT NULL,
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS user_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            access_token TEXT UNIQUE NOT NULL,
            token_type TEXT DEFAULT 'Bearer',
            client_version TEXT DEFAULT '5.354.0',
            issued_at TEXT NOT NULL,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            transcript TEXT,
            meeting_date TEXT,
            duration_minutes INTEGER,
            attendees TEXT,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            config TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()

    # Check if seed data already exists
    existing = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        logger.info("Seeding database with initial data")
        _seed_data(conn)

    conn.close()
    logger.info(f"Database initialized at {db_path}")


def _seed_data(conn):
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    users = [
        ('alice', 'alice@techcorp.io', 'AlicePass123!', 'Alice Johnson', 'pro'),
        ('bob', 'bob@techcorp.io', 'BobPass123!', 'Bob Martinez', 'free'),
        ('charlie', 'charlie@startupxyz.com', 'CharliePass123!', 'Charlie Kim', 'pro'),
        ('diana', 'diana@enterprise.com', 'DianaPass123!', 'Diana Osei', 'enterprise'),
        ('evan', 'evan@freelance.dev', 'EvanPass123!', 'Evan Patel', 'free'),
    ]

    user_ids = {}
    for username, email, password, display_name, plan in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, display_name, plan, created_at) VALUES (?,?,?,?,?,?)",
            (username, email, pw_hash, display_name, plan, now)
        )
        user_ids[username] = cursor.lastrowid

    # Create credential records for each user
    # legacy: kept for v1 API clients still in the wild
    tokens = {}
    for username, uid in user_ids.items():
        token = secrets.token_urlsafe(48)
        tokens[username] = token
        issued = datetime.utcnow().isoformat()
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        cursor.execute(
            "INSERT INTO user_credentials (user_id, access_token, client_version, issued_at, expires_at) VALUES (?,?,?,?,?)",
            (uid, token, '5.354.0', issued, expires)
        )

    # Seed documents for Alice
    alice_docs = [
        (
            "Q1 Product Roadmap Sync",
            "Discussed Q1 priorities: mobile app v2, API rate limiting, and enterprise SSO. Action items assigned to eng leads.",
            "Alice: Let's kick off with the mobile roadmap. Bob: We need to ship v2 by March. Charlie: SSO is blocking 3 enterprise deals.",
            "2025-01-15", 45, '["alice@techcorp.io","bob@techcorp.io","charlie@startupxyz.com"]', '["roadmap","product","q1"]'
        ),
        (
            "Engineering All-Hands January",
            "Covered system reliability improvements, on-call rotation changes, and new hire onboarding for Q1 batch.",
            "Alice: Welcome to the all-hands. This quarter we focus on reliability. Evan: SLO is at 99.2%, target is 99.5%.",
            "2025-01-22", 60, '["alice@techcorp.io","evan@freelance.dev"]', '["engineering","all-hands"]'
        ),
        (
            "Customer Success Review - Acme Corp",
            "Acme Corp expanding usage to 500 seats. Requested custom SLA and dedicated support channel. Contract renewal in 60 days.",
            "Alice: Acme is our biggest account. Diana: They want dedicated support. Alice: We need to loop in sales.",
            "2025-02-03", 30, '["alice@techcorp.io","diana@enterprise.com"]', '["customer","enterprise","renewal"]'
        ),
        (
            "Design Sprint Kickoff",
            "New onboarding flow design sprint starting. Week 1 focused on user research synthesis and persona validation.",
            "Alice: The current onboarding drops 40% of users. Design team presenting new flow concepts.",
            "2025-02-10", 90, '["alice@techcorp.io","bob@techcorp.io"]', '["design","onboarding","sprint"]'
        ),
        (
            "Investor Update Prep",
            "Prepared Q4 metrics deck. ARR growth at 180% YoY. Churn reduced from 4.2% to 2.1%. Series B talking points finalized.",
            "Alice: Series B deck needs to show the retention improvement story clearly. Let's finalize by Thursday.",
            "2025-02-18", 50, '["alice@techcorp.io"]', '["investor","finance","seriesb"]'
        ),
        (
            "Security Review Meeting",
            "Reviewed penetration test results from external auditors. Three medium findings, zero critical. Remediation plan Q2.",
            "Alice: The auditors found issues in the API gateway layer. Evan: We can patch within 2 weeks.",
            "2025-03-01", 40, '["alice@techcorp.io","evan@freelance.dev"]', '["security","audit","compliance"]'
        ),
    ]

    for title, summary, transcript, meeting_date, duration, attendees, tags in alice_docs:
        cursor.execute(
            """INSERT INTO documents (user_id, title, summary, transcript, meeting_date, duration_minutes, attendees, tags, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_ids['alice'], title, summary, transcript, meeting_date, duration, attendees, tags, now, now)
        )

    # Seed documents for Bob
    bob_docs = [
        (
            "Backend API Architecture Review",
            "Decided on GraphQL federation for v2 API. Team aligned on schema-first approach with code generation.",
            "Bob: GraphQL federation solves our microservices API problem. Evan: Performance benchmarks look good.",
            "2025-01-20", 60, '["bob@techcorp.io","evan@freelance.dev"]', '["engineering","architecture","api"]'
        ),
        (
            "Incident Post-Mortem - Jan 28 Outage",
            "3-hour partial outage caused by misconfigured auto-scaling policy. Immediate fix deployed. Long-term: automated policy validation.",
            "Bob: Root cause was the scaling policy change we deployed Tuesday. Evan: Rollback took 45 minutes too long.",
            "2025-01-30", 75, '["bob@techcorp.io","evan@freelance.dev","alice@techcorp.io"]', '["incident","postmortem","reliability"]'
        ),
        (
            "Sprint Planning - Week 8",
            "Sprint goal: complete auth service refactor and mobile push notification implementation. 34 story points committed.",
            "Bob: Auth refactor is critical path for enterprise SSO. Team capacity is 34 points this sprint.",
            "2025-02-24", 45, '["bob@techcorp.io","evan@freelance.dev"]', '["sprint","planning","engineering"]'
        ),
        (
            "Database Migration Strategy",
            "Evaluated zero-downtime migration approach for user table schema changes. Blue-green deployment chosen.",
            "Bob: We need zero downtime for the user table migration. Evan: Blue-green is the safest option.",
            "2025-03-05", 35, '["bob@techcorp.io"]', '["database","migration","infrastructure"]'
        ),
    ]

    for title, summary, transcript, meeting_date, duration, attendees, tags in bob_docs:
        cursor.execute(
            """INSERT INTO documents (user_id, title, summary, transcript, meeting_date, duration_minutes, attendees, tags, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_ids['bob'], title, summary, transcript, meeting_date, duration, attendees, tags, now, now)
        )

    # Seed documents for Charlie
    charlie_docs = [
        (
            "Enterprise Sales Call - MegaCorp",
            "MegaCorp evaluating NoteSync for 2000-seat deployment. Key concerns: data residency EU, SAML SSO, and audit logs.",
            "Charlie: MegaCorp needs EU data residency. That's a 6-month roadmap item. Alice: We should commit to Q3.",
            "2025-01-25", 55, '["charlie@startupxyz.com","alice@techcorp.io","diana@enterprise.com"]', '["sales","enterprise","megacorp"]'
        ),
        (
            "Partnership Discussion - Notion Integration",
            "Notion team interested in bi-directional sync partnership. Technical spec to be shared in 2 weeks.",
            "Charlie: Notion's API team wants to do a native integration. Huge distribution opportunity.",
            "2025-02-07", 40, '["charlie@startupxyz.com"]', '["partnership","notion","integration"]'
        ),
        (
            "Go-to-Market Planning Q2",
            "Q2 GTM focused on product-led growth. Self-serve trial with 14-day limit. Targeting SMB segment initially.",
            "Charlie: PLG motion requires friction-free signup. Let's reduce onboarding to under 3 minutes.",
            "2025-02-20", 50, '["charlie@startupxyz.com","alice@techcorp.io"]', '["gtm","marketing","q2"]'
        ),
    ]

    for title, summary, transcript, meeting_date, duration, attendees, tags in charlie_docs:
        cursor.execute(
            """INSERT INTO documents (user_id, title, summary, transcript, meeting_date, duration_minutes, attendees, tags, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_ids['charlie'], title, summary, transcript, meeting_date, duration, attendees, tags, now, now)
        )

    # Diana and Evan documents
    cursor.execute(
        """INSERT INTO documents (user_id, title, summary, transcript, meeting_date, duration_minutes, attendees, tags, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user_ids['diana'], "Enterprise Onboarding - GlobalBank",
         "GlobalBank starting 5000-seat rollout. Dedicated CSM assigned. Executive sponsor identified.",
         "Diana: GlobalBank is our largest enterprise deal. Executive sponsor is the CTO.",
         "2025-03-10", 60, '["diana@enterprise.com"]', '["enterprise","onboarding","banking"]', now, now)
    )

    cursor.execute(
        """INSERT INTO documents (user_id, title, summary, transcript, meeting_date, duration_minutes, attendees, tags, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user_ids['evan'], "Infrastructure Cost Review",
         "Monthly cloud spend up 23%. Identified 4 optimization opportunities: reserved instances, idle resources, log retention, CDN.",
         "Evan: AWS bill hit $45k last month. We need to optimize before Series B.",
         "2025-03-12", 35, '["evan@freelance.dev","alice@techcorp.io"]', '["infrastructure","cost","aws"]', now, now)
    )

    # Seed integrations
    cursor.execute(
        "INSERT INTO integrations (user_id, service, config, enabled, created_at) VALUES (?,?,?,?,?)",
        (user_ids['alice'], 'notion', json.dumps({'workspace_id': 'ws_abc123', 'database_id': 'db_xyz789'}), 1, now)
    )
    cursor.execute(
        "INSERT INTO integrations (user_id, service, config, enabled, created_at) VALUES (?,?,?,?,?)",
        (user_ids['charlie'], 'slack', json.dumps({'webhook_url': 'https://hooks.slack.com/example', 'channel': '#meeting-notes'}), 1, now)
    )

    conn.commit()
    logger.info("Database seeding complete")