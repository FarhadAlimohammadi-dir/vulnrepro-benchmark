import sqlite3
import bcrypt
import secrets
import os
from flask_login import UserMixin

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            bio TEXT,
            api_key TEXT,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            detail TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_api_key():
    return 'pk_live_' + secrets.token_hex(24)

class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.password_hash = row['password_hash']
        self.display_name = row['display_name'] or row['username']
        self.bio = row['bio'] or ''
        self.api_key = row['api_key']
        self.role = row['role']

def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row)
    return None

def get_user_by_username(username):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if row:
        return User(row)
    return None

def create_user(username, password, display_name=None, role='user'):
    conn = get_db()
    pw_hash = hash_password(password)
    api_key = generate_api_key()
    try:
        conn.execute(
            'INSERT INTO users (username, password_hash, display_name, bio, api_key, role) VALUES (?, ?, ?, ?, ?, ?)',
            (username, pw_hash, display_name or username, '', api_key, role)
        )
        conn.commit()
    finally:
        conn.close()

def update_user_profile(user_id, display_name, bio):
    conn = get_db()
    conn.execute(
        'UPDATE users SET display_name = ?, bio = ? WHERE id = ?',
        (display_name, bio, user_id)
    )
    conn.commit()
    conn.close()

def rotate_api_key(user_id):
    new_key = generate_api_key()
    conn = get_db()
    conn.execute('UPDATE users SET api_key = ? WHERE id = ?', (new_key, user_id))
    conn.commit()
    conn.close()
    return new_key

def get_projects_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

def create_project(owner_id, name, description):
    conn = get_db()
    conn.execute(
        'INSERT INTO projects (owner_id, name, description) VALUES (?, ?, ?)',
        (owner_id, name, description)
    )
    conn.commit()
    conn.close()

def log_action(user_id, action, detail, ip_address):
    conn = get_db()
    conn.execute(
        'INSERT INTO audit_logs (user_id, action, detail, ip_address) VALUES (?, ?, ?, ?)',
        (user_id, action, detail, ip_address)
    )
    conn.commit()
    conn.close()

def get_audit_logs(user_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = get_db()
    rows = conn.execute('SELECT id, username, display_name, role, created_at FROM users').fetchall()
    conn.close()
    return rows

def search_projects(query):
    conn = get_db()
    # Safe parameterized query - no injection possible
    rows = conn.execute(
        'SELECT p.*, u.username as owner FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.name LIKE ? LIMIT 20',
        (f'%{query}%',)
    ).fetchall()
    conn.close()
    return rows