import sqlite3
import hashlib
import os
import logging
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


def get_db(db_path=None):
    if db_path is None:
        db_path = os.environ.get('DATABASE_PATH', '/app/data/teamhub.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000)
    return f"{salt}:{hashed.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(':', 1)
        check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000)
        return check.hex() == hashed
    except Exception:
        return False


def init_db(db_path: str):
    db = get_db(db_path)
    try:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                bio TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                role TEXT DEFAULT 'member',
                team_id INTEGER,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                owner_id INTEGER,
                team_id INTEGER,
                created_at TEXT NOT NULL,
                deadline TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_members (
                project_id INTEGER,
                user_id INTEGER,
                role TEXT DEFAULT 'contributor',
                joined_at TEXT NOT NULL,
                PRIMARY KEY (project_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL
            );
        ''')
        db.commit()
        _seed_data(db)
    finally:
        db.close()


def _seed_data(db):
    existing = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()
    if existing['cnt'] > 0:
        return

    logger.info("Seeding initial data...")

    now = datetime.utcnow().isoformat()

    # Seed teams
    teams = [
        ('Engineering', 'Core engineering team', now),
        ('Design', 'Product design team', now),
        ('Marketing', 'Growth and marketing', now),
    ]
    for t in teams:
        db.execute('INSERT INTO teams (name, description, created_at) VALUES (?, ?, ?)', t)

    # Seed users
    users = [
        ('alice', 'alice@teamhub.io', hash_password('AlicePass123!'), 'Alice Johnson', 'Senior Engineer @ TeamHub. Coffee addict.', '', 'member', 1),
        ('bob', 'bob@teamhub.io', hash_password('BobPass123!'), 'Bob Smith', 'Product Manager. Dog lover.', '', 'member', 2),
        ('charlie', 'charlie@teamhub.io', hash_password('CharliePass123!'), 'Charlie Admin', 'System administrator.', '', 'admin', 1),
        ('diana', 'diana@teamhub.io', hash_password('Diana999!'), 'Diana Prince', 'Frontend developer with 5 years experience.', '', 'member', 1),
        ('evan', 'evan@teamhub.io', hash_password('Evan2024!'), 'Evan Torres', 'DevOps engineer.', '', 'member', 1),
        ('fiona', 'fiona@teamhub.io', hash_password('Fiona567!'), 'Fiona Green', 'UX Designer with a passion for accessibility.', '', 'member', 2),
        ('george', 'george@teamhub.io', hash_password('George888!'), 'George Hill', 'Backend developer specializing in distributed systems.', '', 'member', 1),
        ('hannah', 'hannah@teamhub.io', hash_password('Hannah321!'), 'Hannah White', 'Data scientist and ML enthusiast.', '', 'member', 1),
        ('ivan', 'ivan@teamhub.io', hash_password('Ivan4096!'), 'Ivan Black', 'Security researcher.', '', 'member', 1),
        ('julia', 'julia@teamhub.io', hash_password('Julia777!'), 'Julia Rose', 'Marketing lead.', '', 'member', 3),
    ]
    for u in users:
        db.execute(
            '''INSERT INTO users (username, email, password_hash, display_name, bio, avatar_url, role, team_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (*u, now)
        )

    db.commit()

    # Get user IDs
    alice_id = db.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
    bob_id = db.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
    charlie_id = db.execute("SELECT id FROM users WHERE username='charlie'").fetchone()['id']

    # Seed projects
    statuses = ['active', 'paused', 'completed']
    project_data = [
        ('API Gateway Refactor', 'Migrate legacy API to new gateway architecture', 'active', alice_id, 1),
        ('Dashboard Redesign', 'Complete overhaul of the analytics dashboard', 'active', bob_id, 2),
        ('CI/CD Pipeline', 'Implement automated deployment pipeline', 'completed', charlie_id, 1),
        ('Mobile App v2', 'Next generation mobile application', 'active', alice_id, 1),
        ('Data Warehouse', 'Centralized data storage and analytics platform', 'paused', charlie_id, 1),
        ('Customer Portal', 'Self-service portal for enterprise customers', 'active', bob_id, 2),
        ('Auth Service', 'Centralized authentication microservice', 'completed', alice_id, 1),
        ('Notification Engine', 'Real-time notification delivery system', 'active', alice_id, 1),
        ('Search Integration', 'Full-text search across all content', 'paused', bob_id, 1),
        ('Billing Module', 'Subscription and billing management', 'active', charlie_id, 1),
        ('Analytics Pipeline', 'Stream processing for user analytics', 'active', alice_id, 1),
        ('Admin Console', 'Internal administration tooling', 'completed', charlie_id, 1),
    ]
    for p in project_data:
        db.execute(
            '''INSERT INTO projects (name, description, status, owner_id, team_id, created_at, deadline)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (*p, now, (datetime.utcnow() + timedelta(days=random.randint(30, 180))).isoformat())
        )

    # Seed messages
    messages = [
        (alice_id, bob_id, 'Project kickoff', 'Hey Bob, can we schedule a kickoff for the dashboard project?', now),
        (bob_id, alice_id, 'Re: Project kickoff', 'Sure! How about Thursday at 2pm?', now),
        (charlie_id, alice_id, 'Access review', 'Please review your team access permissions by EOW.', now),
        (alice_id, charlie_id, 'Re: Access review', 'Will do, thanks for the heads up.', now),
        (bob_id, charlie_id, 'Budget approval', 'Can you approve the Q3 tool budget?', now),
    ]
    for m in messages:
        db.execute(
            'INSERT INTO messages (sender_id, recipient_id, subject, body, created_at) VALUES (?, ?, ?, ?, ?)',
            m
        )

    # Seed audit log
    audit_entries = [
        (alice_id, 'login', 'User logged in', '192.168.1.10', now),
        (bob_id, 'login', 'User logged in', '192.168.1.11', now),
        (charlie_id, 'user.create', 'Created user diana', '10.0.0.1', now),
        (charlie_id, 'project.delete', 'Deleted archived project', '10.0.0.1', now),
        (alice_id, 'profile.update', 'Updated display name', '192.168.1.10', now),
    ]
    for a in audit_entries:
        db.execute(
            'INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)',
            a
        )

    db.commit()
    logger.info("Seed data inserted successfully.")