import sqlite3
import os
import bcrypt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "docflow.db")


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            owner_id INTEGER NOT NULL REFERENCES users(id),
            is_public INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_shares (
            document_id INTEGER NOT NULL REFERENCES documents(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            shared_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (document_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            target TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    users = [
        ("alice", "alice@docflow.io", "user", "AlicePass123!"),
        ("bob", "bob@docflow.io", "user", "BobPass123!"),
        ("charlie", "charlie@docflow.io", "admin", "CharliePass123!"),
        ("diana", "diana@docflow.io", "user", "DianaPass999!"),
        ("eve", "eve@docflow.io", "user", "EvePass777!"),
        ("frank", "frank@docflow.io", "user", "FrankPass555!"),
    ]

    for username, email, role, pw in users:
        existing = cur.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if not existing:
            cur.execute(
                "INSERT INTO users (username, email, role, password_hash) VALUES (?,?,?,?)",
                (username, email, role, hash_pw(pw)),
            )
            logger.info("Created user: %s (%s)", username, role)

    conn.commit()

    # Fetch user IDs
    uid = {
        r[0]: r[1]
        for r in cur.execute("SELECT username, id FROM users").fetchall()
    }

    docs = [
        ("Q3 Roadmap", "## Q3 Goals\n\nLaunch v2 API, migrate to new infra.", "alice", True),
        ("Budget 2025", "Confidential financial projections.", "alice", False),
        ("Team Retrospective June", "What went well: CI/CD improvements.", "bob", False),
        ("Public API Docs", "# DocFlow API\n\nRESTful JSON API documentation.", "charlie", True),
        ("Security Checklist", "- Enable 2FA\n- Rotate secrets\n- Review ACLs", "charlie", False),
        ("Product Vision", "Long-term vision for the DocFlow platform.", "diana", True),
        ("Sprint 14 Notes", "Story points completed: 42", "bob", False),
        ("Onboarding Guide", "Welcome to DocFlow! Here is how to get started.", "frank", True),
        ("Architecture Decision Record 007", "Chose SQLite for embedded storage in dev.", "charlie", False),
        ("Release Notes v1.3", "Fixed pagination bug, improved search performance.", "alice", True),
        ("Customer Feedback July", "NPS score: 72. Top request: dark mode.", "diana", False),
        ("Legal Review Notes", "Review of GDPR compliance posture.", "charlie", False),
        ("Marketing Copy Draft", "Bold. Fast. Collaborative. DocFlow.", "eve", True),
        ("Infrastructure Runbook", "Steps to recover from primary DB failure.", "frank", False),
        ("Feature Requests Backlog", "1. Offline mode\n2. PDF export\n3. Webhooks", "alice", False),
    ]

    for title, content, owner, is_public in docs:
        owner_id = uid.get(owner)
        if owner_id:
            existing = cur.execute(
                "SELECT id FROM documents WHERE title=? AND owner_id=?",
                (title, owner_id),
            ).fetchone()
            if not existing:
                cur.execute(
                    "INSERT INTO documents (title, content, owner_id, is_public) VALUES (?,?,?,?)",
                    (title, content, owner_id, int(is_public)),
                )

    conn.commit()

    audit_events = [
        (uid.get("alice"), "login", "session"),
        (uid.get("alice"), "create_document", "doc:1"),
        (uid.get("bob"), "login", "session"),
        (uid.get("charlie"), "login", "session"),
        (uid.get("charlie"), "set_role", "user:diana"),
        (uid.get("alice"), "share_document", "doc:2"),
        (uid.get("bob"), "update_document", "doc:3"),
        (uid.get("diana"), "login", "session"),
        (uid.get("frank"), "login", "session"),
        (uid.get("charlie"), "create_document", "doc:5"),
    ]

    for user_id, action, target in audit_events:
        if user_id:
            cur.execute(
                "INSERT INTO audit_log (user_id, action, target) VALUES (?,?,?)",
                (user_id, action, target),
            )

    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)


if __name__ == "__main__":
    init()