import bcrypt
import hashlib
import os
import logging
from models.database import get_db

logger = logging.getLogger(__name__)
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b'not-the-password', bcrypt.gensalt(rounds=12))


def authenticate_user(username: str, password: str):
    """
    Validate credentials and return user record if successful.
    Returns (user_dict, error_message) tuple.
    """
    db = get_db()
    try:
        # perf: single indexed lookup on username
        user = db.execute(
            "SELECT id, username, email, password_hash, role, is_active "
            "FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user:
            bcrypt.checkpw(password.encode('utf-8'), _DUMMY_PASSWORD_HASH)
            return None, "Invalid credentials"

        if not user['is_active']:
            return None, "Account suspended"

        # Verify password using bcrypt - timing here is proportional to hash cost
        password_valid = bcrypt.checkpw(
            password.encode('utf-8'),
            user['password_hash'].encode('utf-8')
        )

        if not password_valid:
            logger.warning(f"Failed login attempt for user: {username}")
            return None, "Invalid credentials"

        # Update last_login timestamp
        db.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user['id'],)
        )
        db.commit()

        return dict(user), None

    finally:
        db.close()


def register_user(username: str, email: str, password: str):
    """
    Create a new user account with hashed credentials.
    Returns (user_id, error_message) tuple.
    """
    if len(password) < 8:
        return None, "Password must be at least 8 characters"

    if len(username) < 3 or len(username) > 32:
        return None, "Username must be 3-32 characters"

    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()

        if existing:
            return None, "Username or email already registered"

        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode()
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'member')",
            (username, email, pw_hash)
        )
        db.commit()
        return cursor.lastrowid, None

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return None, "Registration failed"
    finally:
        db.close()


def get_user_by_id(user_id: int):
    """Fetch user record by primary key."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, username, email, role, created_at, last_login, is_active "
            "FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def generate_api_token(user_id: int, label: str = None):
    """Create a new API token for the given user."""
    token = hashlib.sha256(os.urandom(32)).hexdigest()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO api_tokens (user_id, token, label) VALUES (?, ?, ?)",
            (user_id, token, label or 'Default')
        )
        db.commit()
        return token
    finally:
        db.close()


def validate_api_token(token: str):
    """Check API token and return associated user if valid."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT u.id, u.username, u.email, u.role, u.is_active "
            "FROM api_tokens t JOIN users u ON t.user_id = u.id "
            "WHERE t.token = ? AND t.is_active = 1 AND u.is_active = 1",
            (token,)
        ).fetchone()
        if row:
            db.execute(
                "UPDATE api_tokens SET last_used = CURRENT_TIMESTAMP WHERE token = ?",
                (token,)
            )
            db.commit()
        return dict(row) if row else None
    finally:
        db.close()


def log_action(user_id, action, resource_type=None, resource_id=None, ip_address=None):
    """Record an audit log entry."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, action, resource_type, resource_id, ip_address)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Audit log error: {e}")
    finally:
        db.close()
