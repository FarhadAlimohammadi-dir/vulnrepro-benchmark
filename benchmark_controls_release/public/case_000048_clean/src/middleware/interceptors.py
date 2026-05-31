import logging
from functools import wraps
from flask import request, jsonify, g
from models.database import verify_token, get_db

logger = logging.getLogger(__name__)

# Public, unauthenticated endpoints. Matched by exact string equality only:
# the health-check status page, the login form/handler, and the public server
# version probe used by load balancers. Any other path requires a bearer
# token (see require_auth below).
PUBLIC_PATHS = frozenset({
    '/status',
    '/login',
    '/app/rest/server',
})


def _is_public_path(path: str) -> bool:
    if not isinstance(path, str):
        return False
    return path in PUBLIC_PATHS


def require_auth(f):
    """
    Decorator that enforces token-based authentication on API routes.
    Routes whose paths match PRE_HANDLING_DISABLED are skipped.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
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
