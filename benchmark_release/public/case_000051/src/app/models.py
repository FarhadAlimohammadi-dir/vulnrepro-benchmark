import sqlite3
import hashlib
import os
import logging
import bcrypt
from flask_login import UserMixin

logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, role, oidc_sub, display_name):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.oidc_sub = oidc_sub
        self.display_name = display_name

    def is_admin(self):
        return self.role == "admin"


def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def db_init(db_path):
    conn = get_db(db_path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            role TEXT DEFAULT 'member',
            oidc_sub TEXT,
            display_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            priority TEXT DEFAULT 'medium',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            assignee_id INTEGER,
            status TEXT DEFAULT 'todo',
            due_date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS oidc_states (
            state TEXT PRIMARY KEY,
            redirect_uri TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    _seed_data(conn, c)
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", db_path)


def _seed_data(conn, c):
    # Check if already seeded
    existing = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    users = [
        ("alice", "alice@taskflow.io", "AlicePass123!", "member", None, "Alice Johnson"),
        ("bob", "bob@taskflow.io", "BobPass123!", "member", None, "Bob Martinez"),
        ("charlie", "charlie@taskflow.io", "CharliePass123!", "admin", None, "Charlie Admin"),
        ("diana", "diana@taskflow.io", "DianaPass456!", "member", None, "Diana Chen"),
        ("eve", "eve@taskflow.io", "EvePass789!", "member", None, "Eve Williams"),
        ("frank", "frank@taskflow.io", "FrankPass321!", "member", "oidc|frank-001", "Frank Thompson"),
        ("grace", "grace@taskflow.io", "GracePass654!", "member", "oidc|grace-002", "Grace Lee"),
    ]

    for username, email, password, role, oidc_sub, display_name in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (username, email, password_hash, role, oidc_sub, display_name) VALUES (?,?,?,?,?,?)",
            (username, email, pw_hash, role, oidc_sub, display_name)
        )

    conn.commit()

    # Get user IDs
    alice_id = c.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
    bob_id = c.execute("SELECT id FROM users WHERE username='bob'").fetchone()[0]
    charlie_id = c.execute("SELECT id FROM users WHERE username='charlie'").fetchone()[0]
    diana_id = c.execute("SELECT id FROM users WHERE username='diana'").fetchone()[0]

    projects = [
        ("Website Redesign", "Complete overhaul of marketing site", alice_id, "active", "high"),
        ("Mobile App v2", "iOS and Android app second version", bob_id, "active", "high"),
        ("API Gateway Migration", "Move from REST to GraphQL", charlie_id, "active", "medium"),
        ("Data Analytics Dashboard", "Real-time metrics platform", diana_id, "active", "medium"),
        ("DevOps Pipeline", "CI/CD automation improvements", alice_id, "completed", "low"),
        ("Customer Portal", "Self-service portal for enterprise clients", bob_id, "active", "high"),
        ("Security Audit Tool", "Internal tool for periodic reviews", charlie_id, "on_hold", "medium"),
        ("ML Model Integration", "Connect prediction models to main app", diana_id, "active", "low"),
        ("Legacy Migration", "Move old PHP services to Python", alice_id, "active", "medium"),
        ("Documentation Hub", "Centralized docs and runbooks", bob_id, "completed", "low"),
    ]

    for name, desc, owner_id, status, priority in projects:
        c.execute(
            "INSERT INTO projects (name, description, owner_id, status, priority) VALUES (?,?,?,?,?)",
            (name, desc, owner_id, status, priority)
        )

    conn.commit()

    proj1 = c.execute("SELECT id FROM projects WHERE name='Website Redesign'").fetchone()[0]
    proj2 = c.execute("SELECT id FROM projects WHERE name='Mobile App v2'").fetchone()[0]
    proj3 = c.execute("SELECT id FROM projects WHERE name='API Gateway Migration'").fetchone()[0]

    tasks = [
        (proj1, "Design mockups", "Create wireframes for all pages", alice_id, "done", "2024-03-01"),
        (proj1, "Frontend development", "Implement React components", alice_id, "in_progress", "2024-04-15"),
        (proj1, "Backend API", "REST endpoints for CMS", bob_id, "todo", "2024-05-01"),
        (proj2, "App architecture", "Define data models and state", bob_id, "done", "2024-02-15"),
        (proj2, "Authentication module", "Implement OAuth login flows", alice_id, "in_progress", "2024-04-20"),
        (proj2, "Push notifications", "Firebase integration", bob_id, "todo", "2024-05-10"),
        (proj3, "Schema design", "GraphQL schema and resolvers", charlie_id, "in_progress", "2024-04-30"),
        (proj3, "Client migration guide", "Documentation for API consumers", diana_id, "todo", "2024-06-01"),
        (proj3, "Performance benchmarks", "Compare REST vs GraphQL latency", bob_id, "todo", "2024-06-15"),
    ]

    for proj_id, title, desc, assignee_id, status, due_date in tasks:
        c.execute(
            "INSERT INTO tasks (project_id, title, description, assignee_id, status, due_date) VALUES (?,?,?,?,?,?)",
            (proj_id, title, desc, assignee_id, status, due_date)
        )

    audit_entries = [
        (charlie_id, "user.created", "user", alice_id, "Created user alice"),
        (charlie_id, "user.created", "user", bob_id, "Created user bob"),
        (alice_id, "project.created", "project", proj1, "Created Website Redesign"),
        (bob_id, "project.created", "project", proj2, "Created Mobile App v2"),
        (charlie_id, "project.created", "project", proj3, "Created API Gateway Migration"),
        (alice_id, "task.updated", "task", 1, "Updated task status to done"),
        (bob_id, "project.updated", "project", proj2, "Changed priority to high"),
        (charlie_id, "user.role_change", "user", diana_id, "Role updated to member"),
    ]

    for user_id, action, res_type, res_id, details in audit_entries:
        c.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)",
            (user_id, action, res_type, res_id, details, "10.0.0.1")
        )


def get_user_by_id(db_path, user_id):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["email"], row["password_hash"],
                    row["role"], row["oidc_sub"], row["display_name"])
    return None


def get_user_by_email(db_path, email):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["email"], row["password_hash"],
                    row["role"], row["oidc_sub"], row["display_name"])
    return None


def get_user_by_username(db_path, username):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["email"], row["password_hash"],
                    row["role"], row["oidc_sub"], row["display_name"])
    return None


def get_user_by_oidc_sub(db_path, sub):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM users WHERE oidc_sub=?", (sub,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["email"], row["password_hash"],
                    row["role"], row["oidc_sub"], row["display_name"])
    return None


def upsert_oidc_user(db_path, sub, email, display_name):
    """Create or update a user record for an OIDC-authenticated identity."""
    conn = get_db(db_path)
    c = conn.cursor()

    # Check by OIDC subject identifier first (most authoritative)
    row = c.execute("SELECT * FROM users WHERE oidc_sub=?", (sub,)).fetchone()
    if row:
        c.execute(
            "UPDATE users SET email=?, display_name=? WHERE oidc_sub=?",
            (email, display_name, sub)
        )
        conn.commit()
        user_id = row["id"]
    else:
        # Check by email for account linking
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            # Link existing account to OIDC subject
            c.execute("UPDATE users SET oidc_sub=? WHERE email=?", (sub, email))
            conn.commit()
            user_id = row["id"]
        else:
            # Provision new account
            username = email.split("@")[0]
            base_username = username
            counter = 1
            while c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
                username = f"{base_username}{counter}"
                counter += 1
            c.execute(
                "INSERT INTO users (username, email, oidc_sub, display_name, role) VALUES (?,?,?,?,?)",
                (username, email, sub, display_name or username, "member")
            )
            conn.commit()
            user_id = c.lastrowid

    user_row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if user_row:
        return User(user_row["id"], user_row["username"], user_row["email"],
                    user_row["password_hash"], user_row["role"],
                    user_row["oidc_sub"], user_row["display_name"])
    return None


def log_audit(db_path, user_id, action, resource_type, resource_id, details, ip):
    conn = get_db(db_path)
    conn.execute(
        "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)",
        (user_id, action, resource_type, resource_id, details, ip)
    )
    conn.commit()
    conn.close()