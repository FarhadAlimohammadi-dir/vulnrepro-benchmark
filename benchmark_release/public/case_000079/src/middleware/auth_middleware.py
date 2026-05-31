import os
import sqlite3
import logging
from functools import wraps
from flask import request, jsonify
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_current_user(token):
    """Resolve a bearer token to a user record."""
    if not token:
        return None
    conn = get_db()
    try:
        row = conn.execute('''
            SELECT u.* FROM users u
            JOIN sessions s ON s.user_id=u.id
            WHERE s.token=? AND u.active=1
            AND (s.expires_at IS NULL OR s.expires_at > ?)
        ''', (token, datetime.utcnow().isoformat())).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def require_auth(f):
    """Decorator: reject requests without a valid Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip()
        user = get_current_user(token)
        if not user:
            return jsonify({'error': 'Authentication required', 'code': 401}), 401
        return f(user, *args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator: restrict endpoint to users with specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user.get('role') not in roles:
                logger.warning(
                    f"Role check failed: user={current_user.get('username')} "
                    f"role={current_user.get('role')} required={roles}"
                )
                return jsonify({'error': 'Insufficient permissions', 'code': 403}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator