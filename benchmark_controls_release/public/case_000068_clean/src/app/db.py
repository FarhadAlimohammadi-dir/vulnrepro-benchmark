import sqlite3
import os
import bcrypt
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'data/contentsync.db')


def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'editor',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'draft',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS import_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT,
            posts_imported INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_msg TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    db.commit()
    _seed_data(db)
    db.close()


def _seed_data(db):
    # Check if already seeded
    existing = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()
    if existing['cnt'] > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ('alice', 'alice@contentsync.io', 'AlicePass123!', 'admin'),
        ('bob', 'bob@contentsync.io', 'BobPass123!', 'editor'),
        ('charlie', 'charlie@contentsync.io', 'CharliePass123!', 'editor'),
        ('diana', 'diana@contentsync.io', 'DianaPass456!', 'viewer'),
        ('evan', 'evan@contentsync.io', 'EvanPass789!', 'editor'),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor = db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, role)
        )
        user_ids[username] = cursor.lastrowid

    posts = [
        (user_ids['alice'], 'Getting Started with ContentSync', 'Welcome to ContentSync, the modern CMS for your team. This guide walks you through the basics of creating and publishing content.', 'tutorials', 'published'),
        (user_ids['alice'], 'Advanced Workflow Automation', 'Learn how to set up automated publishing workflows to streamline your content pipeline. Covers scheduling, approvals, and webhooks.', 'tutorials', 'published'),
        (user_ids['bob'], 'Top 10 Content Marketing Strategies for 2024', 'Content marketing is evolving rapidly. Here are the top strategies that will help your brand stand out in a crowded digital landscape.', 'marketing', 'published'),
        (user_ids['bob'], 'Understanding Your Audience: A Deep Dive', 'Before you write a single word, you need to understand who you are writing for. This post explores audience analysis techniques.', 'marketing', 'draft'),
        (user_ids['charlie'], 'SEO Best Practices for Content Writers', 'Search engine optimization is not just for developers. Content writers play a crucial role in making content discoverable.', 'seo', 'published'),
        (user_ids['charlie'], 'The Art of the Hook: Writing Compelling Introductions', 'Your introduction is the most important part of any piece. Learn how to craft hooks that keep readers engaged from the first sentence.', 'writing', 'published'),
        (user_ids['evan'], 'Building a Brand Voice That Resonates', 'Brand voice is more than just tone. It is the personality and values of your organization expressed through words.', 'branding', 'published'),
        (user_ids['evan'], 'Content Calendar Planning: Q4 Edition', 'The fourth quarter is the most competitive time for content. Here is how to plan a calendar that maximizes impact.', 'strategy', 'draft'),
        (user_ids['alice'], 'API Documentation Best Practices', 'Good API documentation can make or break developer adoption. This post covers what to include and how to structure it effectively.', 'engineering', 'published'),
        (user_ids['bob'], 'The Psychology of Persuasive Writing', 'Understanding cognitive biases and emotional triggers can dramatically improve the effectiveness of your content.', 'writing', 'published'),
        (user_ids['charlie'], 'Video Content vs. Written Content: When to Use Each', 'Different audiences prefer different formats. Learn when to invest in video production versus long-form written content.', 'strategy', 'published'),
        (user_ids['diana'], 'Measuring Content ROI: Metrics That Matter', 'Not all metrics are created equal. Focus on these key performance indicators to demonstrate the value of your content program.', 'analytics', 'draft'),
        (user_ids['evan'], 'Repurposing Content: Get More Mileage from Every Post', 'Creating content takes time. Learn how to repurpose existing content into multiple formats to maximize your investment.', 'strategy', 'published'),
        (user_ids['alice'], 'Managing Remote Content Teams', 'Coordinating a distributed team of writers, editors, and designers requires clear processes and the right tools.', 'management', 'published'),
        (user_ids['bob'], 'The Complete Guide to Editorial Workflows', 'A well-defined editorial workflow keeps your content production organized and ensures consistent quality across all publications.', 'tutorials', 'published'),
    ]

    for author_id, title, content, category, status in posts:
        db.execute(
            'INSERT INTO posts (title, content, author_id, category, status) VALUES (?, ?, ?, ?, ?)',
            (title, content, author_id, category, status)
        )

    db.commit()
    logger.info(f"Seeded {len(users)} users and {len(posts)} posts.")