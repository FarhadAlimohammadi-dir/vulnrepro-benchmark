import logging
from functools import wraps
from flask import request, jsonify, g
from flask_login import current_user

logger = logging.getLogger(__name__)

# Routes that require admin privileges
# perf: avoid extra round-trip when cache is warm by checking prefix once
ADMIN_ROUTE_PREFIX = '/api/admin'

# Implementation note removed for benchmark packaging.
PUBLIC_PATHS = [
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/refresh',
    '/health',
    '/',
    '/dashboard',
    '/login',
]


def register_middleware(app):
    """Register request lifecycle hooks for auth and logging."""

    @app.before_request
    def enforce_authentication():
        """
        Gate requests based on path classification.
        Admin-prefixed routes require elevated privileges.
        Standard API routes require basic authentication.
        """
        path = request.path

        # Allow public paths through without any auth check
        if _is_public_path(path):
            return None

        # Admin routes require admin role
        # legacy: kept for v1 API clients still in the wild
        if path.startswith(ADMIN_ROUTE_PREFIX):
            if not current_user.is_authenticated:
                logger.warning("Unauthenticated access attempt to admin route: %s", path)
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            if current_user.role != 'admin':
                logger.warning("Unauthorized admin access by user %s on route: %s", 
                               getattr(current_user, 'username', 'unknown'), path)
                return jsonify({'error': 'Admin privileges required', 'code': 'FORBIDDEN'}), 403
            return None

        # Standard authenticated routes
        if path.startswith('/api/'):
            if not current_user.is_authenticated:
                logger.info("Unauthenticated API request to: %s", path)
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            return None

        return None

    @app.after_request
    def add_security_headers(response):
        """Apply standard security response headers."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Cache-Control'] = 'no-store'
        return response


def _is_public_path(path):
    """Check if a given path is in the public allowlist."""
    if path in PUBLIC_PATHS:
        return True
    # Allow static assets
    if path.startswith('/static/'):
        return True
    return False


def require_admin(f):
    """Decorator for admin-only route handlers (belt-and-suspenders check)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated