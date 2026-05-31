"""
Authentication and authorization middleware for Flask routes.
"""
from functools import wraps
from flask import session, jsonify, request


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required', 'code': 'UNAUTHENTICATED'}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Allow access if the user has any of the given roles or is admin.
    Usage: @role_required('manager') or @role_required('manager', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_role = session.get('role', '')
            if user_role == 'admin' or user_role in roles:
                return f(*args, **kwargs)
            return jsonify({'error': 'Insufficient permissions', 'required': list(roles)}), 403
        return decorated
    return decorator


def get_current_user():
    return {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
    }


def get_client_ip():
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'