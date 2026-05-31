import hashlib
from db import get_db


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def get_user_by_id(user_id: int):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()


def get_user_by_username(username: str):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()


def authenticate(username: str, password: str):
    db = get_db()
    return db.execute(
        'SELECT id, username, role FROM users WHERE username=? AND password_hash=?',
        (username, hash_password(password))
    ).fetchone()


def update_profile(user_id: int, bio: str, email: str):
    db = get_db()
    db.execute(
        'UPDATE users SET bio=?, email=? WHERE id=?',
        (bio[:500], email[:200], user_id)
    )
    db.commit()


def update_last_login(user_id: int):
    db = get_db()
    db.execute('UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (user_id,))
    db.commit()


def list_users(page: int = 1, per_page: int = 20):
    db = get_db()
    offset = (page - 1) * per_page
    rows = db.execute(
        'SELECT id, username, email, role, bio, created_at, last_login FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    return [dict(r) for r in rows], total