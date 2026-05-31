import jwt
import os
import bcrypt
import logging
from flask import Blueprint, request, jsonify, session
from functools import wraps
from models.db import get_db
from services.token_service import generate_session_token, exchange_actor_token

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/api')

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        if payload.get('role') != 'admin':
            return jsonify({'error': 'Administrator access required'}), 403
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/v1/auth/login', methods=['POST'])
def login():
    """Authenticate user and return session token."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    db = get_db()
    try:
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1",
            (username,)
        ).fetchone()

        if not user:
            logger.warning(f"Login attempt for unknown user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            logger.warning(f"Failed login for user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        db.execute(
            "UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?",
            (user['id'],)
        )
        db.commit()

        token = generate_session_token(
            user_id=user['id'],
            username=user['username'],
            tenant_id=user['tenant_id'],
            role=user['role']
        )

        logger.info(f"User {username} logged in from {request.remote_addr}")
        return jsonify({
            'token': token,
            'username': user['username'],
            'tenant_id': user['tenant_id'],
            'role': user['role'],
            'display_name': user['display_name']
        })
    finally:
        db.close()


@auth_bp.route('/v1/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Invalidate current session."""
    user = request.current_user
    logger.info(f"User {user.get('username')} logged out")
    return jsonify({'status': 'logged out'})


@auth_bp.route('/v1/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Return current authenticated user details."""
    user = request.current_user
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, username, email, tenant_id, role, display_name, created_at, last_login FROM users WHERE id=?",
            (user['sub'],)
        ).fetchone()
        if not row:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(dict(row))
    finally:
        db.close()


@auth_bp.route('/v2/auth/actor', methods=['POST'])
@require_auth
def redeem_actor_token():
    """
    Exchange an integration actor token for a session.
    Service integrations use this endpoint to assume delegated identities
    for cross-tenant operations. Requires an authenticated calling service.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    actor_token = data.get('actor_token')
    if not actor_token:
        return jsonify({'error': 'actor_token required'}), 400

    requesting_user = request.current_user
    result = exchange_actor_token(actor_token, int(requesting_user['sub']))

    if 'error' in result:
        logger.warning(f"Actor token exchange failed: {result['error']} (requester: {requesting_user.get('username')})")
        return jsonify(result), 400

    return jsonify(result)


@auth_bp.route('/v1/auth/refresh', methods=['POST'])
@require_auth
def refresh_token():
    """Refresh an expiring session token."""
    user = request.current_user
    new_token = generate_session_token(
        user_id=int(user['sub']),
        username=user['username'],
        tenant_id=user['tenant_id'],
        role=user['role']
    )
    return jsonify({'token': new_token})