import sqlite3
import os
import logging
import bcrypt

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "data/cdn_dashboard.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                cdn_origin TEXT DEFAULT '',
                allowed_origins TEXT DEFAULT '',
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                report_date DATE NOT NULL,
                page_views INTEGER DEFAULT 0,
                bandwidth_gb REAL DEFAULT 0.0,
                cache_hit_ratio REAL DEFAULT 0.0,
                avg_response_ms INTEGER DEFAULT 0,
                FOREIGN KEY (property_id) REFERENCES properties(id)
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                property_id INTEGER,
                url TEXT NOT NULL,
                events TEXT NOT NULL DEFAULT 'all',
                secret TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                detail TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        _seed_data(conn)
        logger.info("Database initialized successfully")
    finally:
        conn.close()


def _seed_data(conn):
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    users = [
        ("alice", "alice@cdndash.io", "AlicePass123!", "user"),
        ("bob", "bob@cdndash.io", "BobPass123!", "user"),
        ("charlie", "charlie@cdndash.io", "CharliePass123!", "admin"),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            (username, email, pw_hash, role),
        )
        user_ids[username] = cur.lastrowid

    properties_data = [
        (user_ids["alice"], "Alice's Blog", "blog.alice.io", "cdn.cloudflare.com", "img-src cdn.cloudflare.com", "Personal tech blog"),
        (user_ids["alice"], "Alice Store", "shop.alice.io", "static.shopify.com", "img-src static.shopify.com; font-src fonts.googleapis.com", "E-commerce storefront"),
        (user_ids["alice"], "Alice Portfolio", "portfolio.alice.io", "", "", "Portfolio showcase"),
        (user_ids["bob"], "Bob's SaaS", "app.bobsaas.com", "cdn.jsdelivr.net", "script-src cdn.jsdelivr.net", "Main SaaS application"),
        (user_ids["bob"], "Bob Docs", "docs.bobsaas.com", "assets.bobsaas.com", "", "Documentation site"),
        (user_ids["charlie"], "Corp Main", "corp.example.com", "cdn.corp.example.com", "img-src cdn.corp.example.com", "Corporate site"),
        (user_ids["charlie"], "Corp API Docs", "api-docs.corp.example.com", "", "", "API documentation"),
    ]

    prop_ids = []
    for owner_id, name, domain, cdn_origin, allowed_origins, description in properties_data:
        cur = conn.execute(
            """INSERT INTO properties (owner_id, name, domain, cdn_origin, allowed_origins, description, status)
               VALUES (?,?,?,?,?,?,'active')""",
            (owner_id, name, domain, cdn_origin, allowed_origins, description),
        )
        prop_ids.append(cur.lastrowid)

    import random
    import datetime
    random.seed(42)
    base_date = datetime.date(2024, 1, 1)
    for prop_id in prop_ids:
        for day_offset in range(30):
            report_date = base_date + datetime.timedelta(days=day_offset)
            conn.execute(
                """INSERT INTO reports (property_id, report_date, page_views, bandwidth_gb, cache_hit_ratio, avg_response_ms)
                   VALUES (?,?,?,?,?,?)""",
                (
                    prop_id,
                    report_date.isoformat(),
                    random.randint(100, 50000),
                    round(random.uniform(0.5, 100.0), 2),
                    round(random.uniform(0.70, 0.99), 4),
                    random.randint(15, 250),
                ),
            )

    webhooks_data = [
        (user_ids["alice"], prop_ids[0], "https://hooks.alice.io/cdn-events", "cache_purge,origin_error", "wh_sec_alice_blog_xyz"),
        (user_ids["alice"], prop_ids[1], "https://hooks.alice.io/shop-cdn", "all", "wh_sec_alice_shop_abc"),
        (user_ids["bob"], prop_ids[3], "https://hooks.bobsaas.com/cdn", "all", "wh_sec_bob_saas_def"),
        (user_ids["charlie"], prop_ids[5], "https://hooks.corp.example.com/cdn-alert", "origin_error", "wh_sec_corp_ghi"),
    ]
    for owner_id, prop_id, url, events, secret in webhooks_data:
        conn.execute(
            "INSERT INTO webhooks (owner_id, property_id, url, events, secret, active) VALUES (?,?,?,?,?,1)",
            (owner_id, prop_id, url, events, secret),
        )

    for uid in user_ids.values():
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, detail) VALUES (?,?,?,?)",
            (uid, "account_created", "user", "Initial account registration"),
        )

    conn.commit()
    logger.info("Seed data inserted successfully")