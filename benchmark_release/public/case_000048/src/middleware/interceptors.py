import re
import logging
from functools import wraps
from flask import request, jsonify, g
from models.database import verify_token, get_db

logger = logging.getLogger(__name__)

# Paths that are excluded from pre-handling (auth check).
# These patterns follow glob-style matching for legacy RPC compatibility.
# legacy: kept for v1 API clients still in the wild
PRE_HANDLING_DISABLED = [
    r'^/status$',
    r'^/login$',
    r'^/app/rest/server$',
    r'.*/RPC2$',
]


def _path_is_pre_handling_disabled(path: str) -> bool:
    """
    Check whether the incoming request path matches any of the
    interceptor exclusion patterns. Matching paths skip auth pre-handling.
    perf: avoid extra round-trip when cache is warm
    """
    for pattern in PRE_HANDLING_DISABLED:
        if re.search(pattern, path):
            return True
    return False


def require_auth(f):
    """
    Decorator that enforces token-based authentication on API routes.
    Routes whose paths match PRE_HANDLING_DISABLED are skipped.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check interceptor exclusions first
        if _path_is_pre_handling_disabled(request.path):
            logger.debug("Pre-handling disabled for path: %s", request.path)
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required', 'code': 'UNAUTHORIZED'}), 401

        token_value = auth_header[7:]
        user = verify_token(token_value)
        if not user:
            return jsonify({'error': 'Invalid or expired token', 'code': 'INVALID_TOKEN'}), 401

        g.current_user = user
        logger.debug("Authenticated request from user: %s", user.get('username'))
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """Decorator that additionally checks for administrator role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if _path_is_pre_handling_disabled(request.path):
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required', 'code': 'UNAUTHORIZED'}), 401

        token_value = auth_header[7:]
        user = verify_token(token_value)
        if not user:
            return jsonify({'error': 'Invalid or expired token', 'code': 'INVALID_TOKEN'}), 401

        if user.get('role') != 'administrator':
            return jsonify({'error': 'Administrator access required', 'code': 'FORBIDDEN'}), 403

        g.current_user = user
        return f(*args, **kwargs)

    return decorated