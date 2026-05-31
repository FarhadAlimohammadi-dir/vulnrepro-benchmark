import sqlite3
import hashlib
import os
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DB_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db():
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email         TEXT,
            full_name     TEXT,
            role          TEXT NOT NULL DEFAULT 'user',
            department    TEXT DEFAULT 'General',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login    DATETIME
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner       TEXT NOT NULL,
            subject     TEXT NOT NULL,
            body        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'open',
            priority    TEXT NOT NULL DEFAULT 'normal',
            category    TEXT DEFAULT 'general',
            summary     TEXT,
            tags        TEXT DEFAULT '',
            assigned_to TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ticket_comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
            author     TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT,
            action     TEXT,
            details    TEXT,
            ip_addr    TEXT,
            ts         DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kb_articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            category   TEXT DEFAULT 'general',
            author     TEXT,
            views      INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id          INTEGER PRIMARY KEY REFERENCES users(id),
            notify_email     INTEGER DEFAULT 1,
            notify_slack     INTEGER DEFAULT 0,
            theme            TEXT DEFAULT 'light',
            timezone         TEXT DEFAULT 'UTC',
            items_per_page   INTEGER DEFAULT 10
        );
    """)
    conn.commit()
    conn.close()


def seed_data():
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if already seeded
    existing = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    if existing > 0:
        conn.close()
        return

    users = [
        ("alice",   hash_password("alice123"),   "alice@neuraldesk.io",   "Alice Martin",    "user",    "Engineering"),
        ("bob",     hash_password("bob456"),      "bob@neuraldesk.io",     "Bob Thompson",    "user",    "Sales"),
        ("support", hash_password("support789"),  "support@neuraldesk.io", "Support Team",    "support", "Support"),
        ("carol",   hash_password("carol321"),    "carol@neuraldesk.io",   "Carol Davis",     "user",    "Marketing"),
        ("dan",     hash_password("dan654"),      "dan@neuraldesk.io",     "Dan Wilson",      "user",    "Finance"),
        ("eve",     hash_password("eve987"),      "eve@neuraldesk.io",     "Eve Rodriguez",   "user",    "HR"),
        ("frank",   hash_password("frank111"),    "frank@neuraldesk.io",   "Frank Lee",       "support", "Support"),
        ("grace",   hash_password("grace222"),    "grace@neuraldesk.io",   "Grace Kim",       "admin",   "IT"),
    ]

    for username, pw_hash, email, full_name, role, dept in users:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, email, full_name, role, department) VALUES (?,?,?,?,?,?)",
                (username, pw_hash, email, full_name, role, dept)
            )
        except sqlite3.IntegrityError:
            pass

    tickets = [
        ("alice",   "Cannot export CSV report",          "Clicking the export button does nothing in Chrome 124. Tried Firefox — same issue.",          "open",     "high",   "technical"),
        ("alice",   "Two-factor auth not working",       "The 2FA SMS codes are not arriving after the recent update.",                                  "open",     "normal", "account"),
        ("bob",     "Billing charge dispute — March",    "I was charged twice for my March subscription. Invoice #INV-20240312 shows duplicate line.",   "open",     "high",   "billing"),
        ("bob",     "Feature request: bulk close",       "Would be great to bulk-close tickets from the queue view. Saves a lot of clicks.",             "closed",   "low",    "feature"),
        ("carol",   "Dashboard widget missing",          "The SLA compliance widget disappeared from my dashboard after Tuesday's deployment.",          "open",     "normal", "technical"),
        ("carol",   "Password reset email delay",        "Password reset emails are arriving 20-30 minutes late. Customers are frustrated.",             "open",     "high",   "technical"),
        ("dan",     "API rate limit too low",            "Our integration hits the 100 req/min cap during peak hours. Can we get this raised to 500?",   "open",     "normal", "technical"),
        ("dan",     "Expense report integration",        "Need SAP integration for expense reports. Currently doing this manually in spreadsheets.",     "pending",  "low",    "feature"),
        ("eve",     "SSO login broken for new hires",    "New hires added after 2024-04-01 cannot log in via SSO. Existing users are unaffected.",       "open",     "critical","account"),
        ("eve",     "Slack notification not firing",     "Ticket-closed Slack notifications stopped working after the webhook URL was rotated.",         "open",     "normal", "technical"),
        ("frank",   "Queue assignment routing bug",      "Tickets tagged 'billing' are incorrectly routed to the technical queue instead of finance.",   "open",     "high",   "technical"),
        ("grace",   "Audit log export missing fields",   "CSV export of audit log is missing the ip_addr column. Needed for compliance review.",         "closed",   "high",   "technical"),
        ("alice",   "Slow response on search",           "Search results take 8-12 seconds to load when filtering by date range + category together.",   "open",     "normal", "technical"),
        ("bob",     "Multi-language support request",    "Clients in France are requesting French UI. Is there a localization roadmap?",                  "closed",   "low",    "feature"),
        ("carol",   "Report schedule not triggering",   "Weekly PDF reports stopped being emailed on schedule since April 15.",                          "open",     "high",   "technical"),
    ]

    for owner, subject, body, status, priority, category in tickets:
        conn.execute(
            "INSERT INTO tickets (owner, subject, body, status, priority, category) VALUES (?,?,?,?,?,?)",
            (owner, subject, body, status, priority, category)
        )

    articles = [
        ("How to reset your password",          "Navigate to the login page and click 'Forgot Password'. Enter your registered email address and check your inbox for a reset link. The link expires after 24 hours.", "account", "support"),
        ("Understanding ticket priorities",     "Critical: service is completely down. High: major feature broken. Normal: standard request. Low: cosmetic or future enhancement.", "general", "grace"),
        ("Setting up two-factor authentication","Go to Profile > Security > Enable 2FA. Scan the QR code with your authenticator app or enter the setup key manually.", "account", "grace"),
        ("API rate limits explained",           "Free tier: 100 requests/minute. Pro: 500 requests/minute. Enterprise: custom. Rate limit headers are included in every API response.", "technical", "frank"),
        ("Exporting data from NeuralDesk",      "All data exports are available under Settings > Data Export. CSV and JSON formats are supported. Large exports are queued and emailed when ready.", "general", "support"),
    ]

    for title, content, category, author in articles:
        conn.execute(
            "INSERT INTO kb_articles (title, content, category, author) VALUES (?,?,?,?)",
            (title, content, category, author)
        )

    for u in users:
        uid = conn.execute("SELECT id FROM users WHERE username=?", (u[0],)).fetchone()
        if uid:
            try:
                conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (uid["id"],))
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()