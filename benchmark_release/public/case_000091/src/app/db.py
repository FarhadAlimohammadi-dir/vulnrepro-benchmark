import os
import sqlite3
import bcrypt
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DATABASE_PATH", "data/docflow.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    db = get_db()
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                owner_id INTEGER REFERENCES users(id),
                is_public INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER REFERENCES documents(id),
                shared_with_id INTEGER REFERENCES users(id),
                permission TEXT NOT NULL DEFAULT 'read',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id INTEGER,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.commit()
        _seed_data(db)
    except Exception as e:
        logger.error(f"Database init error: {e}")
        raise
    finally:
        db.close()


def _seed_data(db):
    existing = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if existing["cnt"] > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ("alice", "alice@docflow.internal", "AlicePass123!", "admin"),
        ("bob", "bob@docflow.internal", "BobPass123!", "editor"),
        ("charlie", "charlie@docflow.internal", "CharliePass123!", "viewer"),
        ("diana", "diana@docflow.internal", "DianaPass456!", "editor"),
        ("evan", "evan@docflow.internal", "EvanPass789!", "viewer"),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, role)
        )
        user_ids[username] = cur.lastrowid

    categories = [
        ("Engineering", "Technical documentation and specs"),
        ("Legal", "Contracts, compliance docs"),
        ("Marketing", "Campaign assets and brand guidelines"),
        ("HR", "Policies, onboarding materials"),
        ("Finance", "Budgets, reports, invoices"),
    ]
    cat_ids = {}
    for name, desc in categories:
        cur = db.execute(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            (name, desc)
        )
        cat_ids[name] = cur.lastrowid

    documents = [
        ("API Design Guidelines", "## Overview\nAll internal APIs must follow REST conventions...", "Engineering", "alice", 1),
        ("Q3 Budget Forecast", "Revenue targets for Q3 stand at $4.2M...", "Finance", "alice", 0),
        ("Employee Handbook v4", "Welcome to DocFlow Inc. This handbook covers...", "HR", "diana", 1),
        ("NDA Template 2024", "This Non-Disclosure Agreement is entered into...", "Legal", "alice", 0),
        ("Brand Style Guide", "Our primary color palette consists of #1A73E8...", "Marketing", "diana", 1),
        ("Infrastructure Runbook", "## On-call procedures\nSeverity 1 incidents require...", "Engineering", "bob", 0),
        ("GDPR Compliance Checklist", "Data processing activities must be documented...", "Legal", "alice", 0),
        ("Onboarding Checklist", "Day 1: Set up workstation, meet the team...", "HR", "diana", 1),
        ("Marketing Campaign Q4", "Target demographic: 25-40 professionals...", "Marketing", "diana", 0),
        ("Database Schema v3", "The users table contains the following columns...", "Engineering", "bob", 1),
        ("Sales Playbook", "Discovery questions to ask prospective clients...", "Marketing", "bob", 1),
        ("Security Policy", "All employees must use MFA on company accounts...", "HR", "alice", 1),
        ("Vendor Contracts 2024", "Vendor agreements are renewed annually...", "Legal", "alice", 0),
        ("Release Notes v2.4", "### Changes\n- Fixed pagination bug\n- Added CSV export...", "Engineering", "bob", 1),
        ("Expense Report Template", "Use this template for all expense submissions...", "Finance", "diana", 1),
    ]

    for title, content, cat, owner, is_public in documents:
        db.execute(
            "INSERT INTO documents (title, content, category_id, owner_id, is_public) VALUES (?, ?, ?, ?, ?)",
            (title, content, cat_ids[cat], user_ids[owner], is_public)
        )

    audit_actions = [
        (user_ids["alice"], "LOGIN", "session", None, "192.168.1.10"),
        (user_ids["bob"], "VIEW_DOCUMENT", "document", 1, "10.0.0.45"),
        (user_ids["charlie"], "LOGIN", "session", None, "172.16.0.22"),
        (user_ids["alice"], "CREATE_DOCUMENT", "document", 1, "192.168.1.10"),
        (user_ids["diana"], "UPDATE_DOCUMENT", "document", 3, "10.10.1.5"),
        (user_ids["bob"], "EXPORT_DOCUMENT", "document", 6, "10.0.0.45"),
        (user_ids["charlie"], "VIEW_DOCUMENT", "document", 5, "172.16.0.22"),
        (user_ids["alice"], "SHARE_DOCUMENT", "document", 2, "192.168.1.10"),
    ]
    for uid, action, rtype, rid, ip in audit_actions:
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
            (uid, action, rtype, rid, ip)
        )

    db.commit()
    logger.info("Seed data committed.")