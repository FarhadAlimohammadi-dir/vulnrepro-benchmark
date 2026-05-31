import sqlite3
import os
import logging
import bcrypt

logger = logging.getLogger(__name__)

_db_path = None


def get_db_path():
    return _db_path or os.environ.get("DATABASE_PATH", "githost.db")


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str):
    global _db_path
    _db_path = db_path
    logger.info(f"Initializing database at {db_path}")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            );

            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                visibility TEXT DEFAULT 'private',
                default_branch TEXT DEFAULT 'main',
                clone_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS git_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                protocol TEXT NOT NULL,
                host TEXT NOT NULL,
                username TEXT NOT NULL,
                token TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS access_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                scopes TEXT DEFAULT 'read',
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                secret TEXT,
                events TEXT DEFAULT 'push',
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repo_id) REFERENCES repositories(id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        _seed_data(cursor, conn)

    finally:
        conn.close()


def _seed_data(cursor, conn):
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ("alice", "alice@example.com", "AlicePass123!", "admin"),
        ("bob", "bob@example.com", "BobPass123!", "user"),
        ("charlie", "charlie@example.com", "CharliePass123!", "user"),
        ("diana", "diana@example.com", "DianaPass456!", "user"),
        ("eve", "eve@example.com", "EvePass789!", "user"),
        ("frank", "frank@example.com", "FrankPass321!", "user"),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, role),
        )
        user_ids[username] = cursor.lastrowid

    repos = [
        (user_ids["alice"], "api-gateway", "Main API gateway service", "private", "main"),
        (user_ids["alice"], "frontend", "React frontend application", "public", "main"),
        (user_ids["alice"], "infra-scripts", "Infrastructure automation", "private", "master"),
        (user_ids["bob"], "data-pipeline", "ETL pipeline for analytics", "private", "main"),
        (user_ids["bob"], "ml-models", "Machine learning model repository", "private", "main"),
        (user_ids["charlie"], "mobile-app", "iOS/Android mobile application", "private", "develop"),
        (user_ids["charlie"], "design-assets", "UI/UX design files", "public", "main"),
        (user_ids["diana"], "docs", "Technical documentation", "public", "main"),
        (user_ids["frank"], "devtools", "Developer tooling and scripts", "private", "main"),
        (user_ids["frank"], "config-mgmt", "Configuration management", "private", "main"),
    ]

    for owner_id, name, desc, visibility, branch in repos:
        cursor.execute(
            """INSERT INTO repositories (owner_id, name, description, visibility, default_branch, clone_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (owner_id, name, desc, visibility, branch, f"https://githost.example.com/{name}.git"),
        )

    # Stored git credentials (protocol/host pairs with tokens)
    git_creds = [
        (user_ids["alice"], "GitHub personal", "https", "github.com", "alice", "AliceGitHubToken_ghp_abc123secret"),
        (user_ids["alice"], "GitLab work", "https", "gitlab.example.com", "alice_work", "AliceGitLabToken_glpat_xyz789"),
        (user_ids["bob"], "GitHub Bob", "https", "github.com", "bob_dev", "BobGitHubToken_ghp_def456secret"),
        (user_ids["bob"], "Bitbucket Bob", "https", "bitbucket.org", "bobsmith", "BobBBToken_apppass_ghi789"),
        (user_ids["charlie"], "GitHub Charlie", "https", "github.com", "charliec", "CharlieGHToken_ghp_jkl012"),
        (user_ids["diana"], "GitLab Diana", "https", "gitlab.com", "diana_d", "DianaGLToken_glpat_mno345"),
        (user_ids["frank"], "GitHub Frank", "https", "github.com", "frankdev", "FrankGHToken_ghp_pqr678"),
        (user_ids["frank"], "Internal Gitea", "http", "git.internal.corp", "frank", "FrankInternalToken_abc"),
    ]

    for owner_id, label, protocol, host, uname, token in git_creds:
        cursor.execute(
            """INSERT INTO git_credentials (owner_id, label, protocol, host, username, token)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (owner_id, label, protocol, host, uname, token),
        )

    # Access tokens for API usage
    access_tokens = [
        (user_ids["alice"], "CI/CD Pipeline", "tok_alice_cicd_a1b2c3d4e5f6", "read,write"),
        (user_ids["alice"], "Monitoring", "tok_alice_monitor_b2c3d4e5f6a1", "read"),
        (user_ids["bob"], "Deployment Bot", "tok_bob_deploy_c3d4e5f6a1b2", "read,write,deploy"),
        (user_ids["charlie"], "Mobile CI", "tok_charlie_mci_d4e5f6a1b2c3", "read,write"),
        (user_ids["diana"], "Docs Publisher", "tok_diana_docs_e5f6a1b2c3d4", "read"),
        (user_ids["frank"], "Infra Bot", "tok_frank_infra_f6a1b2c3d4e5", "read,write,admin"),
    ]

    for user_id, name, token, scopes in access_tokens:
        cursor.execute(
            "INSERT INTO access_tokens (user_id, name, token, scopes) VALUES (?, ?, ?, ?)",
            (user_id, name, token, scopes),
        )

    webhooks_data = [
        (1, "https://ci.example.com/hook/github", "wh_secret_a1", "push,pr"),
        (1, "https://slack.example.com/services/T00/B00/abc", "wh_secret_b2", "push"),
        (4, "https://jenkins.example.com/generic-webhook-trigger/invoke", "wh_secret_c3", "push,tag"),
        (6, "https://testflight.example.com/hook", "wh_secret_d4", "push"),
    ]

    for repo_id, url, secret, events in webhooks_data:
        cursor.execute(
            "INSERT INTO webhooks (repo_id, url, secret, events) VALUES (?, ?, ?, ?)",
            (repo_id, url, secret, events),
        )

    conn.commit()
    logger.info("Seed data inserted successfully")