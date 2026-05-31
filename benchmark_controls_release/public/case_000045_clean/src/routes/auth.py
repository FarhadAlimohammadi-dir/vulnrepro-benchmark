import logging
import bcrypt
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from models.database import get_db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


def _get_token_from_header():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def _validate_token(token):
    """Validate Bearer token and return user row or None."""
    if not token:
        return None
    db = get_db()
    row = db.execute(
        """SELECT u.* FROM users u
           JOIN user_credentials uc ON uc.user_id = u.id
           WHERE uc.access_token = ? AND (uc.expires_at IS NULL OR uc.expires_at > ?)""",
        (token, datetime.utcnow().isoformat())
    ).fetchone()
    db.close()
    return row


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip().lower()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', username)

    if not username or not email or not password:
        return jsonify({'error': 'username, email, and password are required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters'}), 400

    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()

        if existing:
            return jsonify({'error': 'Username or email already taken'}), 409

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        now = datetime.utcnow().isoformat()

        db.execute(
            "INSERT INTO users (username, email, password_hash, display_name, plan, created_at) VALUES (?,?,?,?,?,?)",
            (username, email, pw_hash, display_name, 'free', now)
        )
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Issue initial access token
        token = secrets.token_urlsafe(48)
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        db.execute(
            "INSERT INTO user_credentials (user_id, access_token, issued_at, expires_at) VALUES (?,?,?,?)",
            (user_id, token, now, expires)
        )
        db.commit()

        logger.info(f"New user registered: {username}")
        return jsonify({
            'message': 'Account created',
            'username': username,
            'access_token': token
        }), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        db.close()


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return access token."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    db = get_db()
    try:
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401

        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return jsonify({'error': 'Invalid credentials'}), 401

        # Rotate token on login
        token = secrets.token_urlsafe(48)
        now = datetime.utcnow().isoformat()
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()

        db.execute(
            "UPDATE user_credentials SET access_token = ?, issued_at = ?, expires_at = ? WHERE user_id = ?",
            (token, now, expires, user['id'])
        )
        db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now, user['id'])
        )
        db.commit()

        logger.info(f"User logged in: {username}")
        return jsonify({
            'access_token': token,
            'token_type': 'Bearer',
            'expires_at': expires,
            'user': {
                'username': user['username'],
                'display_name': user['display_name'],
                'plan': user['plan']
            }
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500
    finally:
        db.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Invalidate the current access token."""
    token = _get_token_from_header()
    if not token:
        return jsonify({'error': 'No token provided'}), 401

    db = get_db()
    try:
        db.execute(
            "UPDATE user_credentials SET expires_at = ? WHERE access_token = ?",
            (datetime.utcnow().isoformat(), token)
        )
        db.commit()
        logger.info("Token invalidated")
        return jsonify({'message': 'Logged out successfully'}), 200
    finally:
        db.close()


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get the authenticated user's profile."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        doc_count = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?", (user['id'],)
        ).fetchone()['cnt']

        return jsonify({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'display_name': user['display_name'],
            'plan': user['plan'],
            'document_count': doc_count,
            'member_since': user['created_at']
        }), 200
    finally:
        db.close()


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update the authenticated user's profile details."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    display_name = data.get('display_name', '').strip()

    if not display_name:
        return jsonify({'error': 'display_name is required'}), 400

    db = get_db()
    try:
        db.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name, user['id'])
        )
        db.commit()
        return jsonify({'message': 'Profile updated', 'display_name': display_name}), 200
    finally:
        db.close()