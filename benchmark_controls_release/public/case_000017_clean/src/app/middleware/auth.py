"""
Authentication and authorization middleware.
"""
from functools import wraps
from flask import session, redirect, url_for, jsonify, request, g
from services.user_service import get_user_by_id


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required.'}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required.'}), 401
            return redirect(url_for('auth.login'))
        user = get_user_by_id(session['user_id'])
        if not user or user.get('role') != 'admin':
            if request.is_json:
                return jsonify({'error': 'Admin access required.'}), 403
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


def inject_current_user():
    """Before-request hook to load the current user into flask.g."""
    if 'user_id' in session:
        g.current_user = get_user_by_id(session['user_id'])
    else:
        g.current_user = None