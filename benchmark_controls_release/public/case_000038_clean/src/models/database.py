import sqlite3
import os
import bcrypt
import logging
import secrets
from flask import g, current_app

logger = logging.getLogger(__name__)


def get_db():
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE_PATH', './data/platform.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def init_db(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            country TEXT DEFAULT 'US',
            role TEXT DEFAULT 'user',
            sso_token TEXT DEFAULT NULL,
            sso_provider TEXT DEFAULT NULL,
            account_status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            genre TEXT,
            price REAL DEFAULT 0.0,
            publisher TEXT,
            release_year INTEGER,
            rating REAL DEFAULT 0.0,
            downloads INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE(user_id, game_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'completed',
            transaction_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_id) REFERENCES games(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            body TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_id) REFERENCES games(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            ip_address TEXT,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            used INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    _seed_data(db)
    db.commit()
    logger.info("Database initialized successfully")


def _seed_data(db):
    existing = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if existing['cnt'] > 0:
        return

    users = [
        ('alice@example.com', 'alice_gamer', os.environ.get('SEED_ALICE_PASSWORD') or secrets.token_urlsafe(18), 'Alice Johnson', 'US', 'admin'),
        ('bob@example.com', 'bob_plays', os.environ.get('SEED_BOB_PASSWORD') or secrets.token_urlsafe(18), 'Bob Smith', 'UK', 'user'),
        ('charlie@example.com', 'charlie_x', os.environ.get('SEED_CHARLIE_PASSWORD') or secrets.token_urlsafe(18), 'Charlie Brown', 'CA', 'user'),
        ('diana@example.com', 'diana_99', os.environ.get('SEED_DIANA_PASSWORD') or secrets.token_urlsafe(18), 'Diana Prince', 'AU', 'user'),
        ('evan@example.com', 'evan_dev', os.environ.get('SEED_EVAN_PASSWORD') or secrets.token_urlsafe(18), 'Evan Torres', 'US', 'user'),
        ('fiona@example.com', 'fiona_fps', os.environ.get('SEED_FIONA_PASSWORD') or secrets.token_urlsafe(18), 'Fiona Green', 'DE', 'user'),
        ('george@example.com', 'george_rpg', os.environ.get('SEED_GEORGE_PASSWORD') or secrets.token_urlsafe(18), 'George Hall', 'FR', 'user'),
        ('hannah@example.com', 'han_plays', os.environ.get('SEED_HANNAH_PASSWORD') or secrets.token_urlsafe(18), 'Hannah White', 'US', 'user'),
        ('ivan@example.com', 'ivan_mmo', os.environ.get('SEED_IVAN_PASSWORD') or secrets.token_urlsafe(18), 'Ivan Petrov', 'RU', 'user'),
        ('julia@example.com', 'julia_rts', os.environ.get('SEED_JULIA_PASSWORD') or secrets.token_urlsafe(18), 'Julia Chen', 'CN', 'user'),
    ]

    for email, username, password, display_name, country, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db.execute(
            """INSERT INTO users (email, username, password_hash, display_name, country, role)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email, username, pw_hash, display_name, country, role)
        )

    games = [
        ('Apex Legends', 'apex-legends', 'Battle royale FPS', 'Battle Royale', 0.0, 'Respawn', 2019, 4.5, 1200000),
        ('Battlefield 2042', 'battlefield-2042', 'Modern warfare FPS', 'FPS', 59.99, 'DICE', 2021, 3.8, 450000),
        ('FIFA 24', 'fifa-24', 'Football simulation', 'Sports', 69.99, 'EA Sports', 2023, 4.1, 890000),
        ('The Sims 4', 'sims-4', 'Life simulation game', 'Simulation', 0.0, 'Maxis', 2014, 4.3, 2100000),
        ('Mass Effect Legendary', 'mass-effect-legendary', 'Epic RPG trilogy', 'RPG', 39.99, 'BioWare', 2021, 4.9, 320000),
        ('Dragon Age Origins', 'dragon-age-origins', 'Fantasy RPG', 'RPG', 19.99, 'BioWare', 2009, 4.8, 280000),
        ('Star Wars Jedi Fallen Order', 'jedi-fallen-order', 'Action adventure', 'Action', 29.99, 'Respawn', 2019, 4.7, 510000),
        ('Need for Speed Heat', 'nfs-heat', 'Street racing game', 'Racing', 29.99, 'Ghost Games', 2019, 4.0, 230000),
        ('Plants vs Zombies', 'pvz-gw2', 'Garden warfare shooter', 'Shooter', 0.0, 'PopCap', 2016, 4.2, 760000),
        ('Titanfall 2', 'titanfall-2', 'Mech FPS game', 'FPS', 9.99, 'Respawn', 2016, 4.9, 190000),
        ('Anthem', 'anthem', 'Co-op action RPG', 'RPG', 14.99, 'BioWare', 2019, 3.1, 140000),
        ('Dead Space Remake', 'dead-space-remake', 'Sci-fi survival horror', 'Horror', 59.99, 'Motive', 2023, 4.6, 280000),
    ]

    for title, slug, desc, genre, price, pub, year, rating, downloads in games:
        db.execute(
            """INSERT INTO games (title, slug, description, genre, price, publisher, release_year, rating, downloads)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, slug, desc, genre, price, pub, year, rating, downloads)
        )

    library_entries = [
        (1, 1), (1, 5), (1, 6), (1, 7),
        (2, 1), (2, 3), (2, 9),
        (3, 2), (3, 4), (3, 10),
        (4, 1), (4, 11),
        (5, 5), (5, 7), (5, 12),
    ]
    for uid, gid in library_entries:
        db.execute(
            "INSERT OR IGNORE INTO user_library (user_id, game_id) VALUES (?, ?)",
            (uid, gid)
        )

    db.commit()
    logger.info("Seed data inserted")


class UserModel:
    def __init__(self, row):
        self.id = row['id']
        self.email = row['email']
        self.username = row['username']
        self.display_name = row['display_name']
        self.country = row['country']
        self.role = row['role']
        self.account_status = row['account_status']
        self.sso_token = row['sso_token']
        self.sso_provider = row['sso_provider']
        self.is_active = row['account_status'] == 'active'
        self.is_authenticated = self.is_active
        self.is_anonymous = False

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get_by_id(db, user_id):
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            return UserModel(row)
        return None

    @staticmethod
    def get_by_email(db, email):
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return UserModel(row)
        return None
