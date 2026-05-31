import os
import sqlite3
import hashlib
import secrets
import logging
from flask import Flask, g
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.admin import admin_bp
from routes.oauth_provider import oauth_provider_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-abc123')

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/collab.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            social_provider TEXT,
            social_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            display_name TEXT,
            avatar_url TEXT,
            plan TEXT DEFAULT 'free'
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            visibility TEXT DEFAULT 'private',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            word_count INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS document_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            shared_with_id INTEGER NOT NULL,
            permission TEXT DEFAULT 'read',
            shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (shared_with_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            user_email TEXT NOT NULL,
            provider TEXT NOT NULL,
            app_id TEXT NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
    ''')

    import bcrypt

    def hash_pw(pw):
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    seed_users = [
        ('alice@example.com', 'alice', hash_pw('AlicePass123!'), 'user', 'Alice Johnson', 'free'),
        ('bob@example.com', 'bob', hash_pw('BobPass123!'), 'user', 'Bob Smith', 'pro'),
        ('charlie@example.com', 'charlie', hash_pw('CharliePass123!'), 'admin', 'Charlie Admin', 'enterprise'),
        ('diana@example.com', 'diana', hash_pw('DianaPass456!'), 'user', 'Diana Prince', 'free'),
        ('eve@example.com', 'eve', hash_pw('EvePass789!'), 'user', 'Eve Wilson', 'pro'),
        ('frank@example.com', 'frank', hash_pw('FrankPass321!'), 'user', 'Frank Miller', 'free'),
        ('grace@example.com', 'grace', hash_pw('GracePass654!'), 'user', 'Grace Lee', 'pro'),
    ]

    for email, username, pw_hash, role, display_name, plan in seed_users:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO users (email, username, password_hash, role, display_name, plan) VALUES (?, ?, ?, ?, ?, ?)',
                (email, username, pw_hash, role, display_name, plan)
            )
        except Exception as e:
            logger.warning(f"Seed user {email} already exists: {e}")

    seed_docs = [
        (1, 'Q4 Marketing Strategy', 'Our Q4 marketing plan focuses on...', 'private', 342),
        (1, 'Product Roadmap 2024', 'Key initiatives for next year include...', 'shared', 891),
        (2, 'Technical Architecture Notes', 'The microservices architecture we plan...', 'private', 567),
        (2, 'API Integration Guide', 'Steps for integrating with our REST API...', 'public', 1203),
        (3, 'Admin Procedures Manual', 'Internal procedures for system administration...', 'private', 445),
        (3, 'Security Audit Report', 'Findings from the annual security review...', 'private', 789),
        (1, 'Meeting Notes - Oct 2023', 'Attendees: Alice, Bob, Charlie...', 'shared', 234),
        (4, 'Personal Portfolio Draft', 'My professional experience includes...', 'private', 612),
        (5, 'Research Notes', 'Literature review on machine learning...', 'private', 1456),
        (6, 'Budget Proposal', 'FY2024 budget breakdown by department...', 'private', 378),
        (7, 'Conference Presentation', 'Slide deck for the upcoming conference...', 'shared', 523),
        (2, 'Database Schema v2', 'Updated schema with new tables...', 'private', 234),
        (1, 'Client Onboarding Checklist', 'Steps to onboard a new enterprise client...', 'shared', 445),
        (3, 'Compliance Documentation', 'GDPR compliance measures implemented...', 'private', 876),
    ]

    user_rows = conn.execute('SELECT id FROM users ORDER BY id').fetchall()
    user_ids = [r[0] for r in user_rows]

    if user_ids:
        for i, (_, title, content, visibility, wc) in enumerate(seed_docs):
            owner_id = user_ids[i % len(user_ids)]
            try:
                conn.execute(
                    'INSERT OR IGNORE INTO documents (owner_id, title, content, visibility, word_count) VALUES (?, ?, ?, ?, ?)',
                    (owner_id, title, content, visibility, wc)
                )
            except Exception as e:
                logger.warning(f"Seed doc error: {e}")

    # Seed oauth tokens for the mock provider (issued to app_id "third-party-app")
    mock_tokens = [
        ('mock_token_alice_001', 'alice@example.com', 'google', 'third-party-app'),
        ('mock_token_bob_001', 'bob@example.com', 'google', 'third-party-app'),
        ('attacker_token_999', 'attacker@evil.com', 'google', 'third-party-app'),
    ]
    for token, email, provider, app_id in mock_tokens:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO oauth_tokens (token, user_email, provider, app_id) VALUES (?, ?, ?, ?)',
                (token, email, provider, app_id)
            )
        except Exception as e:
            logger.warning(f"Seed token error: {e}")

    conn.commit()
    conn.close()
    logger.info("Database initialized and seeded.")

app.config['DATABASE_PATH'] = DATABASE_PATH
app.config['get_db'] = get_db

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(documents_bp, url_prefix='/api/documents')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(oauth_provider_bp, url_prefix='/mock-oauth')

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'CollabDocs API'}, 200

@app.route('/')
def index():
    return {'service': 'CollabDocs', 'version': '2.1.0', 'docs': '/api/docs'}, 200

if __name__ == '__main__':
    init_db()
    logger.info("Starting CollabDocs API on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)