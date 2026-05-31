"""
User profile and account management helpers.
"""
import hashlib
import re
from flask import g


def get_db():
    return g.db


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def get_user_by_id(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    return dict(row) if row else None


def update_profile(user_id, display_name, bio, email):
    db = get_db()
    # Basic validation
    if len(display_name) > 64:
        raise ValueError('Display name too long.')
    if len(bio) > 500:
        raise ValueError('Bio must be 500 characters or fewer.')
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise ValueError('Invalid email address.')
    db.execute(
        'UPDATE users SET display_name=?, bio=?, email=? WHERE id=?',
        (display_name, bio, email, user_id)
    )
    db.commit()


def change_password(user_id, current_pw, new_pw):
    db = get_db()
    row = db.execute(
        'SELECT password_hash FROM users WHERE id=?', (user_id,)
    ).fetchone()
    if not row or row['password_hash'] != hash_pw(current_pw):
        raise ValueError('Current password is incorrect.')
    if len(new_pw) < 8:
        raise ValueError('New password must be at least 8 characters.')
    db.execute(
        'UPDATE users SET password_hash=? WHERE id=?',
        (hash_pw(new_pw), user_id)
    )
    db.commit()


def list_users(page=1, per_page=20):
    db = get_db()
    offset = (page - 1) * per_page
    rows = db.execute(
        'SELECT id, username, display_name, role, email, created_at FROM users '
        'ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    return [dict(r) for r in rows], total


def get_unread_notifications(user_id):
    db = get_db()
    rows = db.execute(
        'SELECT * FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def mark_notifications_read(user_id):
    db = get_db()
    db.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (user_id,))
    db.commit()