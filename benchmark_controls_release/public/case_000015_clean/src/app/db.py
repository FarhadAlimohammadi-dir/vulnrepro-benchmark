import sqlite3
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_PATH = os.environ.get("DB_PATH", "/tmp/noteflow.db")


def get_db(path=None):
    path = path or _DEFAULT_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db(path=None):
    path = path or _DEFAULT_PATH
    logger.info("Initialising database at %s", path)
    conn = get_db(path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            email      TEXT DEFAULT '',
            bio        TEXT DEFAULT '',
            role       TEXT DEFAULT 'member',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id   INTEGER NOT NULL REFERENCES users(id),
            title      TEXT NOT NULL,
            body       TEXT NOT NULL DEFAULT '',
            tags       TEXT DEFAULT '',
            public     INTEGER DEFAULT 0,
            views      INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id    INTEGER NOT NULL REFERENCES notes(id),
            author_id  INTEGER NOT NULL REFERENCES users(id),
            body       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            actor      TEXT NOT NULL,
            action     TEXT NOT NULL,
            target     TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
    """)

    # -----------------------------------------------------------------------
    # Seed users
    # -----------------------------------------------------------------------
    seed_users = [
        ("alice",   "alice123",   "alice@noteflow.local",   "Platform admin and chief note-taker.", "admin"),
        ("bob",     "bob456",     "bob@noteflow.local",     "Backend engineer, avid Markdown fan.", "member"),
        ("carol",   "carol789",   "carol@noteflow.local",   "Technical writer and documentation lead.", "member"),
        ("dave",    "dave321",    "dave@noteflow.local",    "Product manager.", "member"),
        ("eve",     "eve654",     "eve@noteflow.local",     "Security researcher.", "member"),
        ("frank",   "frank111",   "frank@noteflow.local",   "DevOps engineer.", "member"),
        ("grace",   "grace222",   "grace@noteflow.local",   "Data analyst.", "member"),
        ("henry",   "henry333",   "henry@noteflow.local",   "Frontend developer.", "member"),
    ]
    for uname, pw, email, bio, role in seed_users:
        try:
            c.execute(
                "INSERT INTO users (username, password, email, bio, role) VALUES (?,?,?,?,?)",
                (uname, _hash(pw), email, bio, role),
            )
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Seed notes
    # -----------------------------------------------------------------------
    seed_notes = [
        (1, "Welcome to NoteFlow",
         "**NoteFlow** is your personal Markdown workspace.\n\n"
         "- Write notes in Markdown\n- Share them publicly\n- Discuss with comments\n\n"
         "Bare URLs like docs.noteflow.local/start are auto-linked for convenience.",
         "welcome,docs", 1),
        (1, "Markdown Reference",
         "# Headings\n\n## Sub-heading\n\n**Bold** and *italic* text.\n\n`inline code`\n\n"
         "Fenced blocks and tables coming soon.",
         "markdown,reference", 1),
        (2, "Flask Deployment Notes",
         "Deploy with gunicorn: `gunicorn -w 4 app:app`\n\n"
         "Set SECRET_KEY via environment variable.\n\nSee flask.palletsprojects.com for docs.",
         "flask,deployment", 1),
        (2, "SQLite Performance Tips",
         "Enable WAL mode: `PRAGMA journal_mode=WAL;`\n\n"
         "Use `PRAGMA synchronous=NORMAL;` for better write throughput.\n\n"
         "Index foreign keys to avoid full-table scans.",
         "sqlite,performance", 0),
        (3, "Documentation Style Guide",
         "1. Use active voice.\n2. Keep sentences short.\n3. Define acronyms on first use.\n\n"
         "Reference: developers.google.com/style",
         "docs,style", 1),
        (3, "Meeting Notes 2025-01-14",
         "Attendees: alice, bob, carol\n\nAction items:\n- Bob to deploy v2 by Friday\n"
         "- Carol to update onboarding docs\n- Alice to review access controls",
         "meetings", 0),
        (4, "Q1 Roadmap",
         "## Goals\n\n- Launch public API\n- Add tag-based filtering\n- Improve mobile layout\n\n"
         "Timeline: see projectboard.internal/q1",
         "roadmap,planning", 1),
        (5, "Research Links",
         "Interesting reads this week:\n\n"
         "- portswigger.net/research\n- googleprojectzero.blogspot.com\n- cve.mitre.org",
         "research,security", 1),
        (6, "CI/CD Pipeline Setup",
         "Stages: build → test → deploy\n\nDocker image: python:3.12-slim\n\n"
         "See github.com/noteflow/infra for the full workflow definition.",
         "devops,ci", 0),
        (7, "Dashboard Metrics",
         "Active users (30d): 847\nNotes created (30d): 3,241\n\nTop tag: `development`",
         "analytics", 0),
        (8, "CSS Variables Cheatsheet",
         "`--color-primary: #0070f3`\n`--color-muted: #888`\n`--radius: 6px`\n\n"
         "Import with `@import url('tokens.css')`",
         "frontend,css", 1),
    ]
    for owner_id, title, body, tags, public in seed_notes:
        try:
            c.execute(
                "INSERT INTO notes (owner_id, title, body, tags, public) VALUES (?,?,?,?,?)",
                (owner_id, title, body, tags, public),
            )
        except Exception:
            pass

    # Seed tags
    for tag in ["welcome", "docs", "markdown", "flask", "sqlite", "meetings",
                 "roadmap", "research", "devops", "analytics", "frontend", "css"]:
        try:
            c.execute("INSERT INTO tags (name) VALUES (?)", (tag,))
        except Exception:
            pass

    conn.commit()
    conn.close()
    logger.info("Database ready")