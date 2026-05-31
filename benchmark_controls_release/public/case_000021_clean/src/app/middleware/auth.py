import hashlib
import hmac
import secrets
from functools import wraps
from flask import session, jsonify, request, redirect, url_for
from app.db import get_connection


def ensure_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def csrf_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        supplied = request.headers.get('X-CSRF-Token', '')
        if not supplied:
            form = request.form if request.form else {}
            supplied = form.get('_csrf_token', '')
        expected = session.get('_csrf_token', '')
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return jsonify({'error': 'Invalid or missing CSRF token'}), 400
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            if session.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_password(password_plain, stored_hash):
    return hashlib.sha256(password_plain.encode()).hexdigest() == stored_hash