import sqlite3
import bcrypt
import logging
import os
from flask import g, current_app

logger = logging.getLogger(__name__)


def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def init_db():
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'pipeline.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'contributor',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            script_ref TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by INTEGER,
            approved_at DATETIME,
            approved_script_snapshot TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            dispatched_by INTEGER NOT NULL,
            script_ref TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            FOREIGN KEY (submission_id) REFERENCES submissions(id),
            FOREIGN KEY (dispatched_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES submissions(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed users
    users = [
        ('alice', 'alice@example.com', 'AlicePass123!', 'admin'),
        ('bob', 'bob@example.com', 'BobPass123!', 'contributor'),
        ('charlie', 'charlie@example.com', 'CharliePass123!', 'contributor'),
        ('diana', 'diana@example.com', 'DianaPass999!', 'maintainer'),
        ('eve', 'eve@example.com', 'EvePass777!', 'contributor'),
        ('frank', 'frank@example.com', 'FrankPass555!', 'contributor'),
    ]

    for username, email, password, role in users:
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (username, email, pw_hash, role)
            )

    conn.commit()

    # Seed submissions
    alice_id = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
    bob_id = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
    charlie_id = conn.execute("SELECT id FROM users WHERE username='charlie'").fetchone()['id']
    diana_id = conn.execute("SELECT id FROM users WHERE username='diana'").fetchone()['id']
    eve_id = conn.execute("SELECT id FROM users WHERE username='eve'").fetchone()['id']

    sample_submissions = [
        ('Update npm dependencies', 'Bumps lodash from 4.17.19 to 4.17.21', 'refs/heads/fix/npm-deps-01', bob_id, 'approved', alice_id),
        ('Add Python 3.12 support', 'Updates CI matrix to include Python 3.12', 'refs/heads/feat/py312-support', charlie_id, 'approved', diana_id),
        ('Fix Docker base image', 'Updates base image to python:3.12-slim', 'refs/heads/fix/docker-base', bob_id, 'pending', None),
        ('Bump requests to 2.31', 'Security update for requests library', 'refs/heads/chore/bump-requests', eve_id, 'approved', alice_id),
        ('Add integration tests', 'New test suite for ecosystem integrations', 'refs/heads/feat/integration-tests', charlie_id, 'rejected', alice_id),
        ('Update GitHub Actions', 'Pins actions to SHA instead of tags', 'refs/heads/chore/pin-actions', bob_id, 'pending', None),
        ('Fix memory leak in parser', 'Addresses heap allocation in parser module', 'refs/heads/fix/parser-memory', eve_id, 'pending', None),
        ('Add rate limiting', 'Implements per-IP rate limiting middleware', 'refs/heads/feat/rate-limiting', charlie_id, 'approved', diana_id),
        ('Refactor auth module', 'Splits auth into separate concerns', 'refs/heads/refactor/auth-split', bob_id, 'pending', None),
        ('Update README', 'Improves documentation for new contributors', 'refs/heads/docs/readme-update', eve_id, 'approved', alice_id),
    ]

    for title, desc, script_ref, author_id, status, approved_by in sample_submissions:
        existing = conn.execute('SELECT id FROM submissions WHERE title = ?', (title,)).fetchone()
        if not existing:
            approved_at = 'CURRENT_TIMESTAMP' if approved_by else None
            conn.execute(
                '''INSERT INTO submissions (title, description, script_ref, author_id, status, approved_by, approved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (title, desc, script_ref, author_id, status, approved_by,
                 '2024-01-15 10:00:00' if approved_by else None)
            )

    conn.commit()

    # Seed some jobs
    sub1 = conn.execute("SELECT id FROM submissions WHERE title='Update npm dependencies'").fetchone()
    if sub1:
        existing_job = conn.execute('SELECT id FROM jobs WHERE submission_id = ?', (sub1['id'],)).fetchone()
        if not existing_job:
            conn.execute(
                '''INSERT INTO jobs (submission_id, dispatched_by, script_ref, status, result)
                   VALUES (?, ?, ?, ?, ?)''',
                (sub1['id'], alice_id, 'refs/heads/fix/npm-deps-01', 'completed', 'All tests passed (47/47)')
            )

    sub2 = conn.execute("SELECT id FROM submissions WHERE title='Add Python 3.12 support'").fetchone()
    if sub2:
        existing_job = conn.execute('SELECT id FROM jobs WHERE submission_id = ?', (sub2['id'],)).fetchone()
        if not existing_job:
            conn.execute(
                '''INSERT INTO jobs (submission_id, dispatched_by, script_ref, status, result)
                   VALUES (?, ?, ?, ?, ?)''',
                (sub2['id'], diana_id, 'refs/heads/feat/py312-support', 'completed', 'All tests passed (123/123)')
            )

    # Seed audit logs
    audit_entries = [
        (alice_id, 'submission.approved', 'submission', 1, '{"reason": "Looks good"}'),
        (diana_id, 'submission.approved', 'submission', 2, '{"reason": "CI passes"}'),
        (alice_id, 'job.dispatched', 'job', 1, '{"queue": "integration"}'),
        (bob_id, 'submission.created', 'submission', 3, '{}'),
        (alice_id, 'submission.rejected', 'submission', 5, '{"reason": "Needs more tests"}'),
    ]

    for actor_id, action, resource_type, resource_id, metadata in audit_entries:
        existing = conn.execute(
            'SELECT id FROM audit_log WHERE actor_id=? AND action=? AND resource_id=?',
            (actor_id, action, resource_id)
        ).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO audit_log (actor_id, action, resource_type, resource_id, metadata) VALUES (?, ?, ?, ?, ?)',
                (actor_id, action, resource_type, resource_id, metadata)
            )

    conn.commit()
    conn.close()
    logger.info("Database initialized with seed data")