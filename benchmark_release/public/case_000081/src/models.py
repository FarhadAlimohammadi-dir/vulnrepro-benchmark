import sqlite3
import bcrypt
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)

DB_PATH = 'data/affilitrack.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.email = row['email']
        self.role = row['role']
        self.company = row['company']
        self.created_at = row['created_at']

    def is_admin(self):
        return self.role == 'admin'


def get_user_by_id(user_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        return User(row) if row else None


def get_user_by_username(username):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        return row


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                company TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                commission_rate REAL DEFAULT 0.05,
                status TEXT DEFAULT 'active',
                owner_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_id INTEGER REFERENCES partners(id),
                referrer TEXT,
                ip_address TEXT,
                user_agent TEXT,
                destination_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                click_id INTEGER REFERENCES clicks(id),
                partner_id INTEGER REFERENCES partners(id),
                amount REAL,
                commission REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                message TEXT NOT NULL,
                read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Seed users
        users = [
            ('alice', 'alice@affilitrack.io', 'AlicePass123!', 'admin', 'AffiliTrack Inc.'),
            ('bob', 'bob@partner-network.com', 'BobPass123!', 'user', 'Partner Network LLC'),
            ('charlie', 'charlie@growthco.io', 'CharliePass123!', 'user', 'GrowthCo'),
            ('diana', 'diana@shopboost.com', 'DianaPass456!', 'user', 'ShopBoost'),
            ('evan', 'evan@clickmax.net', 'EvanPass789!', 'user', 'ClickMax'),
        ]
        for username, email, password, role, company in users:
            existing = conn.execute(
                'SELECT id FROM users WHERE username = ?', (username,)
            ).fetchone()
            if not existing:
                pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                conn.execute(
                    'INSERT INTO users (username, email, password_hash, role, company) VALUES (?,?,?,?,?)',
                    (username, email, pw_hash, role, company)
                )

        # Seed partners
        partners = [
            ('TechGadgets Store', 'techgadgets.example.com', 0.07, 'active', 1),
            ('Fashion Hub', 'fashionhub.example.com', 0.09, 'active', 2),
            ('Book World', 'bookworld.example.com', 0.06, 'active', 3),
            ('Fitness Pro', 'fitnesspro.example.com', 0.08, 'active', 4),
            ('Home Decor Plus', 'homedecorplus.example.com', 0.05, 'active', 5),
            ('Electronics Depot', 'electronicsdepot.example.com', 0.04, 'inactive', 2),
            ('Sports Unlimited', 'sportsunlimited.example.com', 0.10, 'active', 3),
            ('Beauty Essentials', 'beautyessentials.example.com', 0.12, 'active', 4),
            ('Office Supplies Co', 'officesupplies.example.com', 0.03, 'pending', 1),
            ('Travel Deals Hub', 'traveldeals.example.com', 0.11, 'active', 5),
        ]
        existing_partners = conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0]
        if existing_partners == 0:
            conn.executemany(
                'INSERT INTO partners (name, domain, commission_rate, status, owner_id) VALUES (?,?,?,?,?)',
                partners
            )

        # Seed clicks
        existing_clicks = conn.execute('SELECT COUNT(*) FROM clicks').fetchone()[0]
        if existing_clicks == 0:
            clicks = [
                (1, 'https://google.com', '10.0.0.1', 'Mozilla/5.0', 'https://techgadgets.example.com/product/123'),
                (2, 'https://bing.com', '10.0.0.2', 'Chrome/120', 'https://fashionhub.example.com/summer-sale'),
                (3, None, '10.0.0.3', 'Safari/17', 'https://bookworld.example.com/bestsellers'),
                (1, 'https://twitter.com', '10.0.0.4', 'Firefox/121', 'https://techgadgets.example.com/deals'),
                (4, 'https://facebook.com', '10.0.0.5', 'Edge/120', 'https://fitnesspro.example.com/equipment'),
                (5, None, '10.0.0.6', 'Mozilla/5.0', 'https://homedecorplus.example.com/living-room'),
                (2, 'https://instagram.com', '10.0.0.7', 'Chrome/119', 'https://fashionhub.example.com/new-arrivals'),
                (7, 'https://reddit.com', '10.0.0.8', 'Firefox/120', 'https://sportsunlimited.example.com/sale'),
                (8, None, '10.0.0.9', 'Safari/16', 'https://beautyessentials.example.com/skincare'),
                (10, 'https://pinterest.com', '10.0.0.10', 'Chrome/120', 'https://traveldeals.example.com/europe'),
            ]
            conn.executemany(
                'INSERT INTO clicks (partner_id, referrer, ip_address, user_agent, destination_url) VALUES (?,?,?,?,?)',
                clicks
            )

        # Seed notifications
        existing_notifs = conn.execute('SELECT COUNT(*) FROM notifications').fetchone()[0]
        if existing_notifs == 0:
            notifs = [
                (1, 'New partner application from ShopBoost received.', 0),
                (2, 'Your commission for October has been processed.', 0),
                (3, 'New conversion recorded for Book World.', 1),
                (1, 'System maintenance scheduled for Sunday 2AM UTC.', 0),
                (4, 'Your partner status has been approved.', 1),
                (5, 'New click milestone: 1000 clicks this month!', 0),
            ]
            conn.executemany(
                'INSERT INTO notifications (user_id, message, read) VALUES (?,?,?)',
                notifs
            )

        logger.info('Database initialized with seed data')