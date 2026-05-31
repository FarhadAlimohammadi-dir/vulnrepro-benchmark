"""
Authentication middleware and decorators.
"""
import hmac
import secrets
from functools import wraps
from flask import session, redirect, url_for, jsonify, request, abort


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'admin':
            return 'Forbidden', 403
        return f(*args, **kwargs)
    return decorated


def get_csrf_token() -> str:
    token = session.get('_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf'] = token
    return token


def verify_csrf():
    expected = session.get('_csrf')
    submitted = request.form.get('_csrf') or request.headers.get('X-CSRF-Token')
    if not expected or not submitted or not hmac.compare_digest(str(expected), str(submitted)):
        abort(400)
