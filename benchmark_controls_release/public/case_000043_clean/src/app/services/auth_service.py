import bcrypt
import logging
from app.database import get_connection

logger = logging.getLogger(__name__)


def authenticate_user(username: str, password: str):
    """Verify username and password, return user dict or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if row is None:
            logger.warning(f"Login attempt for unknown user: {username!r}")
            return None

        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            logger.warning(f"Failed login attempt for user: {username!r}")
            return None

        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        conn.commit()

        logger.info(f"Successful login for user: {username!r}")
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
        }
    finally:
        conn.close()


def get_user_by_token(token: str):
    """Resolve an API access token to a user record."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT u.id, u.username, u.email, u.role
               FROM access_tokens t
               JOIN users u ON t.user_id = u.id
               WHERE t.token = ?
               AND (t.expires_at IS NULL OR t.expires_at > CURRENT_TIMESTAMP)""",
            (token,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def register_user(username: str, email: str, password: str) -> int:
    """Create a new user account. Returns the new user ID."""
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, pw_hash),
        )
        conn.commit()
        logger.info(f"Registered new user: {username!r} (id={cursor.lastrowid})")
        return cursor.lastrowid
    finally:
        conn.close()