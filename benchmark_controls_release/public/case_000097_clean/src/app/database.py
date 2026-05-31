import sqlite3
import os
import bcrypt

DB_PATH = os.environ.get("DB_PATH", "data/cloudsync.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS drive_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            access_token TEXT NOT NULL,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS imported_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            mime_type TEXT,
            size INTEGER,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS mock_drive_files (
            file_id TEXT PRIMARY KEY,
            owner_token TEXT NOT NULL,
            title TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            download_url TEXT,
            body_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _seed_data(c)
    conn.commit()
    conn.close()


def _seed_data(c):
    users = [
        ("alice", "alice@example.com", "AlicePass123!", "user"),
        ("bob", "bob@example.com", "BobPass123!", "user"),
        ("charlie", "charlie@example.com", "CharliePass123!", "admin"),
        ("diana", "diana@example.com", "DianaPass456!", "user"),
        ("eve", "eve@example.com", "EvePass789!", "user"),
    ]

    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            c.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, pw_hash, role),
            )
        except sqlite3.IntegrityError:
            pass

    alice_id = c.execute("SELECT id FROM users WHERE username='alice'").fetchone()
    bob_id = c.execute("SELECT id FROM users WHERE username='bob'").fetchone()
    charlie_id = c.execute("SELECT id FROM users WHERE username='charlie'").fetchone()

    if alice_id:
        projects_data = [
            ("Q4 Marketing Assets", "Design files for Q4 campaign", alice_id[0]),
            ("Product Screenshots", "App screenshots for app store", alice_id[0]),
            ("Brand Guidelines 2024", "Updated brand kit", alice_id[0]),
        ]
        for name, desc, owner in projects_data:
            try:
                c.execute(
                    "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
                    (name, desc, owner),
                )
            except Exception:
                pass

    if bob_id:
        projects_data = [
            ("Sales Deck 2024", "Quarterly sales presentations", bob_id[0]),
            ("Customer Logos", "Partner and customer logo files", bob_id[0]),
        ]
        for name, desc, owner in projects_data:
            try:
                c.execute(
                    "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
                    (name, desc, owner),
                )
            except Exception:
                pass

    drive_tokens = [
        (1, "ya29.alice_token_abc123"),
        (2, "ya29.bob_token_def456"),
        (3, "ya29.charlie_token_ghi789"),
    ]
    for user_id, token in drive_tokens:
        try:
            c.execute(
                "INSERT INTO drive_connections (user_id, access_token) VALUES (?, ?)",
                (user_id, token),
            )
        except Exception:
            pass

    mock_files = [
        (
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs",
            "ya29.alice_token_abc123",
            "company_logo.png",
            "image/png",
            204800,
            "https://www.googleapis.com/download/drive/v2/files/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs?alt=media",
            None,
        ),
        (
            "1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345",
            "ya29.alice_token_abc123",
            "banner_hero.png",
            "image/png",
            512000,
            "https://www.googleapis.com/download/drive/v2/files/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345?alt=media",
            None,
        ),
        (
            "1ZyXwVuTsRqPoNmLkJiHgFeDcBa987654",
            "ya29.bob_token_def456",
            "sales_q4.png",
            "image/png",
            98304,
            "https://www.googleapis.com/download/drive/v2/files/1ZyXwVuTsRqPoNmLkJiHgFeDcBa987654?alt=media",
            None,
        ),
        (
            "1DocSlideImportTestFileId00000001",
            "ya29.charlie_token_ghi789",
            "product_roadmap.png",
            "image/png",
            307200,
            "https://www.googleapis.com/download/drive/v2/files/1DocSlideImportTestFileId00000001?alt=media",
            None,
        ),
    ]

    for fid, token, title, mime, size, dl_url, body in mock_files:
        try:
            c.execute(
                """INSERT INTO mock_drive_files
                   (file_id, owner_token, title, mime_type, file_size, download_url, body_content)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fid, token, title, mime, size, dl_url, body),
            )
        except sqlite3.IntegrityError:
            pass

    audit_entries = [
        (1, "login", "session", "192.168.1.10"),
        (1, "project.create", "projects/1", "192.168.1.10"),
        (2, "login", "session", "10.0.0.5"),
        (3, "login", "session", "172.16.0.1"),
        (3, "admin.audit_view", "audit_log", "172.16.0.1"),
        (1, "drive.list", "drive/files", "192.168.1.10"),
        (2, "drive.list", "drive/files", "10.0.0.5"),
        (1, "file.import", "imported_files/1", "192.168.1.10"),
    ]
    for uid, action, resource, ip in audit_entries:
        try:
            c.execute(
                "INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)",
                (uid, action, resource, ip),
            )
        except Exception:
            pass