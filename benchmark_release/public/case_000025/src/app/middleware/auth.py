from functools import wraps
from flask import session, redirect, url_for, jsonify, request


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthenticated"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                return redirect(url_for("tickets.dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator