import sqlite3
import os
import logging
import bcrypt
import secrets
import string

logger = logging.getLogger(__name__)

_db_path = None


def get_db_path():
    return _db_path


def get_connection():
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def generate_api_key(prefix="phub"):
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(32))
    return f"{prefix}_{token}"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def init_db(db_path: str):
    global _db_path
    _db_path = db_path

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                api_key TEXT UNIQUE NOT NULL,
                api_secret TEXT UNIQUE NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                visibility TEXT NOT NULL DEFAULT 'private',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(project_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id INTEGER,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                notifications_email INTEGER DEFAULT 1,
                notifications_slack INTEGER DEFAULT 0,
                timezone TEXT DEFAULT 'UTC',
                theme TEXT DEFAULT 'light',
                two_factor_enabled INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                secret TEXT NOT NULL,
                events TEXT NOT NULL DEFAULT 'push,pr',
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)

        # Seed users if not present
        users_to_seed = [
            ('alice', 'alice@projecthub.io', 'AlicePass123!', 'admin', 'pro'),
            ('bob', 'bob@projecthub.io', 'BobPass123!', 'member', 'free'),
            ('charlie', 'charlie@projecthub.io', 'CharliePass123!', 'member', 'free'),
            ('diana', 'diana@projecthub.io', 'DianaPass456!', 'member', 'pro'),
            ('eve', 'eve@projecthub.io', 'EvePass789!', 'member', 'free'),
            ('frank', 'frank@projecthub.io', 'FrankPass321!', 'admin', 'enterprise'),
        ]

        for username, email, password, role, plan in users_to_seed:
            existing = cur.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not existing:
                ph = hash_password(password)
                ak = generate_api_key("phub")
                api_secret = generate_api_key("secret")
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, role, api_key, api_secret, plan)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (username, email, ph, role, ak, api_secret, plan)
                )

        conn.commit()

        # Seed projects
        alice_id = cur.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
        bob_id = cur.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
        charlie_id = cur.execute("SELECT id FROM users WHERE username='charlie'").fetchone()['id']
        frank_id = cur.execute("SELECT id FROM users WHERE username='frank'").fetchone()['id']

        existing_projects = cur.execute("SELECT COUNT(*) as c FROM projects").fetchone()['c']
        if existing_projects == 0:
            projects_data = [
                ('Alpha Platform', 'Core infrastructure project', alice_id, 'active', 'private'),
                ('Beta Dashboard', 'Customer-facing analytics dashboard', alice_id, 'active', 'public'),
                ('CI/CD Pipeline', 'Automated deployment pipeline', bob_id, 'active', 'private'),
                ('Mobile App v2', 'Next generation mobile application', charlie_id, 'active', 'private'),
                ('Data Warehouse', 'Analytics data warehouse migration', frank_id, 'active', 'private'),
                ('API Gateway', 'Unified API gateway service', alice_id, 'archived', 'private'),
                ('Auth Service', 'Authentication microservice', bob_id, 'active', 'private'),
                ('Billing Module', 'Subscription and billing logic', frank_id, 'active', 'private'),
                ('Content CDN', 'Global content delivery setup', charlie_id, 'active', 'public'),
                ('DevOps Tooling', 'Internal devops automation', alice_id, 'active', 'private'),
            ]
            for name, desc, owner_id, status, visibility in projects_data:
                cur.execute(
                    """INSERT INTO projects (name, description, owner_id, status, visibility)
                       VALUES (?, ?, ?, ?, ?)""",
                    (name, desc, owner_id, status, visibility)
                )

        conn.commit()

        # Seed settings
        all_users = cur.execute("SELECT id FROM users").fetchall()
        for user_row in all_users:
            uid = user_row['id']
            existing_settings = cur.execute(
                "SELECT id FROM user_settings WHERE user_id=?", (uid,)
            ).fetchone()
            if not existing_settings:
                cur.execute(
                    """INSERT INTO user_settings (user_id, notifications_email, timezone, theme)
                       VALUES (?, 1, 'UTC', 'light')""",
                    (uid,)
                )

        conn.commit()

        # Seed audit logs
        existing_logs = cur.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()['c']
        if existing_logs == 0:
            log_entries = [
                (alice_id, 'user.login', 'user', alice_id, '10.0.0.1'),
                (alice_id, 'project.create', 'project', 1, '10.0.0.1'),
                (bob_id, 'user.login', 'user', bob_id, '10.0.0.2'),
                (bob_id, 'project.create', 'project', 3, '10.0.0.2'),
                (charlie_id, 'user.login', 'user', charlie_id, '10.0.0.3'),
                (alice_id, 'api_key.rotate', 'user', alice_id, '10.0.0.1'),
                (frank_id, 'user.login', 'user', frank_id, '10.0.0.4'),
                (frank_id, 'project.create', 'project', 5, '10.0.0.4'),
                (alice_id, 'project.update', 'project', 2, '10.0.0.1'),
                (bob_id, 'webhook.create', 'webhook', 1, '10.0.0.2'),
            ]
            for uid, action, rtype, rid, ip in log_entries:
                cur.execute(
                    """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address)
                       VALUES (?, ?, ?, ?, ?)""",
                    (uid, action, rtype, rid, ip)
                )

        conn.commit()
        logger.info("Database seeded successfully")

    finally:
        conn.close()