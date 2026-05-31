import os
import sqlite3
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("cloudpanel")

DB_PATH = os.environ.get("DB_PATH", "/app/data/cloudpanel.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            assigned_to INTEGER,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            label TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    _seed_data(conn)
    conn.close()


def _seed_data(conn):
    import bcrypt
    import secrets

    users = [
        ("alice", "alice@cloudpanel.io", "AlicePass123!", "admin"),
        ("bob", "bob@cloudpanel.io", "BobPass123!", "member"),
        ("charlie", "charlie@cloudpanel.io", "CharliePass123!", "member"),
        ("diana", "diana@cloudpanel.io", "DianaPass456!", "member"),
        ("eve", "eve@cloudpanel.io", "EvePass456!", "member"),
    ]

    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            (username, email, pw_hash, role)
        )
    conn.commit()

    alice_id = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()["id"]
    bob_id = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()["id"]
    charlie_id = conn.execute("SELECT id FROM users WHERE username='charlie'").fetchone()["id"]

    projects = [
        ("Alpha Launch", "Q1 product launch campaign", alice_id, "active"),
        ("Backend Refactor", "Migrate to microservices", bob_id, "active"),
        ("Marketing Site v2", "Redesign landing pages", charlie_id, "active"),
        ("Data Pipeline", "ETL overhaul for analytics", alice_id, "archived"),
        ("Mobile App", "iOS and Android client", bob_id, "active"),
        ("Compliance Audit", "SOC2 preparation", alice_id, "active"),
        ("DevOps Automation", "CI/CD improvements", charlie_id, "active"),
    ]

    for name, desc, owner, status in projects:
        conn.execute(
            "INSERT OR IGNORE INTO projects (name, description, owner_id, status) VALUES (?,?,?,?)",
            (name, desc, owner, status)
        )
    conn.commit()

    proj1 = conn.execute("SELECT id FROM projects WHERE name='Alpha Launch'").fetchone()
    if proj1:
        tasks = [
            (proj1["id"], "Write press release", alice_id, "high", "open"),
            (proj1["id"], "Update pricing page", bob_id, "medium", "open"),
            (proj1["id"], "QA smoke tests", charlie_id, "high", "in_progress"),
            (proj1["id"], "Notify beta users", alice_id, "low", "done"),
            (proj1["id"], "Deploy to production", bob_id, "high", "open"),
            (proj1["id"], "Monitor error rates", charlie_id, "medium", "open"),
            (proj1["id"], "Post-launch retrospective", alice_id, "low", "open"),
            (proj1["id"], "Update documentation", bob_id, "medium", "open"),
        ]
        for t in tasks:
            conn.execute(
                "INSERT OR IGNORE INTO tasks (project_id, title, assigned_to, priority, status) VALUES (?,?,?,?,?)",
                t
            )

    for uid in [alice_id, bob_id, charlie_id]:
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT OR IGNORE INTO api_tokens (user_id, token, label) VALUES (?,?,?)",
            (uid, token, "default")
        )
    conn.commit()


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-cloudpanel-2024")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Please sign in to continue."

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.projects import projects_bp
    from app.routes.admin import admin_bp
    from app.routes.profile import profile_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(profile_bp, url_prefix="/profile")

    return app