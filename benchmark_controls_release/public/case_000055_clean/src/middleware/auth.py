from functools import wraps
from flask import session, jsonify

# TODO: replace session cookies with short-lived JWTs for stateless scaling

def login_required(f):
    """Decorator that rejects unauthenticated requests with 401."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated