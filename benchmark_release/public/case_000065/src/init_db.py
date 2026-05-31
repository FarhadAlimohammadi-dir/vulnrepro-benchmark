import sqlite3
import os
import hashlib
import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'trackflow.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'analyst',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    budget REAL DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tracking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    ref TEXT,
    utm_source TEXT,
    utm_campaign TEXT,
    page_url TEXT,
    user_agent TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    date TEXT,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue REAL DEFAULT 0.0,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource TEXT,
    details TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")

# Seed users
users = [
    ('alice', 'alice@trackflow.io', 'AlicePass123!', 'admin'),
    ('bob', 'bob@trackflow.io', 'BobPass123!', 'analyst'),
    ('charlie', 'charlie@trackflow.io', 'CharliePass123!', 'analyst'),
    ('diana', 'diana@trackflow.io', 'DianaPass456!', 'analyst'),
    ('eve', 'eve@trackflow.io', 'EvePass789!', 'viewer'),
]

for username, email, password, role in users:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (username, email, pw_hash, role)
    )

# Seed campaigns
campaigns = [
    (1, 'Summer Sale 2024', 'google', 'cpc', 'summer_sale_2024', 15000.0, 'active'),
    (1, 'Brand Awareness Q3', 'facebook', 'display', 'brand_q3_2024', 8500.0, 'active'),
    (2, 'Email Retargeting', 'email', 'email', 'retarget_july', 3200.0, 'paused'),
    (2, 'Influencer Collab', 'instagram', 'social', 'influencer_aug', 12000.0, 'active'),
    (3, 'Search Expansion', 'bing', 'cpc', 'search_exp_2024', 5400.0, 'active'),
    (3, 'Video Campaign', 'youtube', 'video', 'video_q3', 22000.0, 'active'),
    (1, 'Affiliate Program', 'affiliate', 'affiliate', 'affiliate_q3', 1800.0, 'active'),
    (2, 'Programmatic Display', 'dv360', 'programmatic', 'prog_display', 31000.0, 'active'),
]

for owner_id, name, src, medium, campaign, budget, status in campaigns:
    cur.execute(
        "INSERT OR IGNORE INTO campaigns (owner_id, name, utm_source, utm_medium, utm_campaign, budget, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner_id, name, src, medium, campaign, budget, status)
    )

# Seed analytics
import random
random.seed(42)
for cid in range(1, 9):
    for day in range(1, 16):
        date = f"2024-07-{day:02d}"
        cur.execute(
            "INSERT OR IGNORE INTO analytics_snapshots (campaign_id, date, impressions, clicks, conversions, revenue) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, date, random.randint(1000, 50000), random.randint(50, 2000),
             random.randint(1, 100), round(random.uniform(50, 5000), 2))
        )

# Seed tracking events
refs = ['google_organic', 'facebook_ad', 'newsletter_july', 'direct', 'twitter_post',
        'partner_site_a', 'partner_site_b', 'bing_organic', 'linkedin_post', 'reddit_thread']
pages = ['/pricing', '/features', '/about', '/blog/post-1', '/signup', '/contact']

for i in range(20):
    cur.execute(
        "INSERT INTO tracking_events (session_id, ref, utm_source, utm_campaign, page_url, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
        (f"sess_{i:04d}", random.choice(refs), random.choice(['google', 'fb', 'email']),
         f"campaign_{random.randint(1,8)}", random.choice(pages), f"10.0.{i}.1")
    )

conn.commit()
conn.close()
print("Database initialized with seed data.")