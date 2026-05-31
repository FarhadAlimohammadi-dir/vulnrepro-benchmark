"""
Authentication middleware helpers.
TODO: replace session cookie auth with short-lived JWT once SSO is wired up.
"""
from functools import wraps
from flask import session, jsonify


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*allowed_roles):
    """Decorator that restricts access to users whose role is in allowed_roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Unauthorized"}), 401
            if session.get("role") not in allowed_roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator