import sqlite3
import os
import bcrypt
import logging
import secrets
from flask import g, current_app
from flask_login import UserMixin

logger = logging.getLogger(__name__)


def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db_path = current_app.config['DATABASE_PATH']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            author_id INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            tags TEXT,
            filename TEXT NOT NULL,
            preview_image TEXT,
            downloads INTEGER NOT NULL DEFAULT 0,
            rating_sum INTEGER NOT NULL DEFAULT 0,
            rating_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            engine_version TEXT NOT NULL DEFAULT '1.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(theme_id, user_id),
            FOREIGN KEY (theme_id) REFERENCES themes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (theme_id) REFERENCES themes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def seed_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if already seeded
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if row['cnt'] > 0:
        conn.close()
        return

    logger.info("Seeding database with initial data...")

    users = [
        ('alice', 'alice@themeshop.io', os.environ.get('SEED_ALICE_PASSWORD') or secrets.token_urlsafe(18), 'user'),
        ('bob', 'bob@themeshop.io', os.environ.get('SEED_BOB_PASSWORD') or secrets.token_urlsafe(18), 'user'),
        ('charlie', 'charlie@themeshop.io', os.environ.get('SEED_CHARLIE_PASSWORD') or secrets.token_urlsafe(18), 'admin'),
        ('diana', 'diana@themeshop.io', os.environ.get('SEED_DIANA_PASSWORD') or secrets.token_urlsafe(18), 'user'),
        ('evan', 'evan@themeshop.io', os.environ.get('SEED_EVAN_PASSWORD') or secrets.token_urlsafe(18), 'user'),
        ('fiona', 'fiona@themeshop.io', os.environ.get('SEED_FIONA_PASSWORD') or secrets.token_urlsafe(18), 'user'),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, role)
        )
        user_ids[username] = cur.lastrowid

    # Seed themes with realistic data
    themes_data = [
        ('Midnight Blue', 'A sleek dark theme with blue accents', 'bob', 'dark', 'dark,blue,minimal', 'midnight_blue.zip', 'approved', '1.0'),
        ('Solar Flare', 'Bright orange and yellow sunset theme', 'diana', 'light', 'light,warm,colorful', 'solar_flare.zip', 'approved', '1.0'),
        ('Forest Walk', 'Nature-inspired greens and browns', 'evan', 'nature', 'nature,green,calm', 'forest_walk.zip', 'approved', '1.0'),
        ('Neon City', 'Cyberpunk-style neon colors', 'bob', 'dark', 'dark,neon,cyberpunk', 'neon_city.zip', 'approved', '2.0'),
        ('Arctic Ice', 'Cool whites and light blues', 'fiona', 'light', 'light,minimal,clean', 'arctic_ice.zip', 'approved', '1.0'),
        ('Retro Wave', '80s inspired purple and pink theme', 'diana', 'retro', 'retro,purple,pink', 'retro_wave.zip', 'approved', '2.0'),
        ('Sakura', 'Japanese cherry blossom theme', 'evan', 'nature', 'nature,pink,japanese', 'sakura.zip', 'approved', '1.0'),
        ('Deep Space', 'Dark theme with galaxy imagery', 'fiona', 'dark', 'dark,space,stars', 'deep_space.zip', 'approved', '2.0'),
        ('Terracotta', 'Earthy warm red and brown tones', 'bob', 'earth', 'earth,warm,minimal', 'terracotta.zip', 'pending', '1.0'),
        ('Ocean Breeze', 'Calm sea blues and teals', 'alice', 'nature', 'nature,blue,calm', 'ocean_breeze.zip', 'approved', '1.0'),
        ('Monochrome', 'Classic black and white', 'charlie', 'minimal', 'minimal,bw,classic', 'monochrome.zip', 'approved', '1.0'),
        ('Amber Glow', 'Warm amber and golden tones', 'diana', 'light', 'light,amber,warm', 'amber_glow.zip', 'approved', '1.0'),
        ('Storm Cloud', 'Grey and dark storm aesthetic', 'evan', 'dark', 'dark,grey,moody', 'storm_cloud.zip', 'approved', '2.0'),
        ('Lavender', 'Soft purple lavender tones', 'fiona', 'light', 'light,purple,soft', 'lavender.zip', 'approved', '1.0'),
        ('Obsidian', 'Ultra dark minimal black theme', 'charlie', 'dark', 'dark,minimal,black', 'obsidian.zip', 'approved', '2.0'),
    ]

    for name, desc, author, cat, tags, fname, status, engine in themes_data:
        conn.execute(
            """INSERT INTO themes (name, description, author_id, category, tags, filename, status, engine_version, downloads, rating_sum, rating_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, desc, user_ids[author], cat, tags, fname, status, engine,
             __import__('random').randint(50, 5000),
             __import__('random').randint(10, 50),
             __import__('random').randint(3, 12))
        )

    # Seed audit log entries
    audit_entries = [
        (user_ids['alice'], 'login', 'session', None, 'User logged in', '192.168.1.10'),
        (user_ids['bob'], 'upload_theme', 'theme', 1, 'Uploaded Midnight Blue', '10.0.0.5'),
        (user_ids['charlie'], 'approve_theme', 'theme', 1, 'Theme approved by admin', '10.0.0.1'),
        (user_ids['diana'], 'rate_theme', 'theme', 2, 'Rated Solar Flare 5/5', '172.16.0.8'),
        (user_ids['evan'], 'activate_theme', 'theme', 3, 'Activated Forest Walk', '192.168.2.22'),
        (user_ids['alice'], 'update_profile', 'user', user_ids['alice'], 'Updated email', '192.168.1.10'),
    ]

    for uid, action, ttype, tid, details, ip in audit_entries:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, target_type, target_id, details, ip_address) VALUES (?,?,?,?,?,?)",
            (uid, action, ttype, tid, details, ip)
        )

    conn.commit()
    conn.close()
    logger.info("Database seeding complete")


class User(UserMixin):
    def __init__(self, id, username, email, role, active=True):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.active = active

    @staticmethod
    def get_by_id(user_id):
        from flask import current_app
        db_path = current_app.config['DATABASE_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['active'])
        return None

    @staticmethod
    def get_by_username(username):
        from flask import current_app
        db_path = current_app.config['DATABASE_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
        conn.close()
        if row:
            return row
        return None

    def is_admin(self):
        return self.role == 'admin'
