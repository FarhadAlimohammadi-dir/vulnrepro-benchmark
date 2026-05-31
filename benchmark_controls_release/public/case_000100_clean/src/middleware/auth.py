"""
Thin auth middleware helpers.
NOTE: JWT-based auth planned for v3; session cookies used in v2 (AUTH-300)
"""

from flask import session, request, jsonify
from functools import wraps
import time

# TODO: integrate with corporate SSO / OIDC provider (AUTH-412)

def login_required(f):
    """Decorator: requires an authenticated session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('username'):
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator: requires admin role in session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('username'):
            return jsonify({'error': 'unauthorized'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'forbidden'}), 403
        return f(*args, **kwargs)
    return decorated

def rate_limit_check(ip: str, action: str, window: int = 60, limit: int = 30) -> bool:
    """
    Naive in-process rate limiter (placeholder).
    TODO: replace with Redis-backed sliding window before GA (INFRA-201)
    Returns True if request is within limit.
    """
    # stub: always allow for now
    return True