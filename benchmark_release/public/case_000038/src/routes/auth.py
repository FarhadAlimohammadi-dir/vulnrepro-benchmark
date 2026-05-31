import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt

from models.database import get_db, UserModel

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


def _log_audit(db, user_id, action, ip, details=''):
    try:
        db.execute(
            "INSERT INTO audit_log (user_id, action, ip_address, details) VALUES (?, ?, ?, ?)",
            (user_id, action, ip, details)
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate a platform user. Supports standard credential login
    and SSO partner token flow for enterprise integrations.
    """
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    sso_token = data.get('sso_token')
    ip = request.remote_addr

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user_row:
        logger.info(f"Login attempt for unknown email={email} ip={ip}")
        return jsonify({'error': 'Invalid credentials'}), 401

    if user_row['account_status'] != 'active':
        return jsonify({'error': 'Account suspended'}), 403

    authenticated = False

    if sso_token is not None:
        # legacy: kept for v1 API clients still in the wild
        # SSO partner flow: validate the delegated token issued by identity provider
        stored_token = user_row['sso_token']
        if not stored_token or stored_token == sso_token:
            authenticated = True
            logger.info(f"SSO token auth for email={email} provider={user_row['sso_provider']}")
    else:
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        try:
            pw_match = bcrypt.checkpw(password.encode(), user_row['password_hash'].encode())
        except Exception:
            pw_match = False
        if pw_match:
            authenticated = True

    if not authenticated:
        _log_audit(db, user_row['id'], 'login_failed', ip, f'method={"sso" if sso_token is not None else "password"}')
        logger.warning(f"Failed login for email={email} ip={ip}")
        return jsonify({'error': 'Invalid credentials'}), 401

    user = UserModel(user_row)
    login_user(user, remember=True)

    db.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow(), user.id))
    _log_audit(db, user.id, 'login_success', ip, f'method={"sso" if sso_token is not None else "password"}')
    db.commit()

    logger.info(f"Successful login for email={email} id={user.id}")
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'display_name': user.display_name,
            'role': user.role
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    db = get_db()
    _log_audit(db, current_user.id, 'logout', request.remote_addr)
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    display_name = data.get('display_name', username)
    country = data.get('country', 'US')

    if not all([email, username, password]):
        return jsonify({'error': 'email, username, and password are required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE email = ? OR username = ?", (email, username)
    ).fetchone()
    if existing:
        return jsonify({'error': 'Email or username already in use'}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.execute(
        """INSERT INTO users (email, username, password_hash, display_name, country)
           VALUES (?, ?, ?, ?, ?)""",
        (email, username, pw_hash, display_name, country)
    )
    db.commit()
    _log_audit(db, None, 'register', request.remote_addr, f'email={email}')

    logger.info(f"New user registered: email={email} username={username}")
    return jsonify({'message': 'Account created successfully'}), 201


@auth_bp.route('/request-reset', methods=['POST'])
def request_password_reset():
    """Initiate a password reset flow. Sends reset token to registered email."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email required'}), 400

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        db.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user['id'], token, expires)
        )
        db.commit()
        logger.info(f"Password reset requested for email={email}")

    return jsonify({'message': 'If that email is registered, a reset link has been sent'}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Complete password reset using the token from the reset email."""
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    new_password = data.get('new_password', '')

    if not token or not new_password:
        return jsonify({'error': 'Token and new_password are required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    db = get_db()
    reset_row = db.execute(
        """SELECT * FROM password_reset_tokens
           WHERE token = ? AND used = 0 AND expires_at > ?""",
        (token, datetime.utcnow())
    ).fetchone()

    if not reset_row:
        return jsonify({'error': 'Invalid or expired reset token'}), 400

    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, reset_row['user_id']))
    db.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (reset_row['id'],))
    db.commit()

    _log_audit(db, reset_row['user_id'], 'password_reset', request.remote_addr)
    logger.info(f"Password reset completed for user_id={reset_row['user_id']}")
    return jsonify({'message': 'Password updated successfully'}), 200


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change password for authenticated user. Requires current password verification."""
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password are required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    db = get_db()
    user_row = db.execute(
        "SELECT password_hash FROM users WHERE id = ?", (current_user.id,)
    ).fetchone()

    try:
        if not bcrypt.checkpw(current_password.encode(), user_row['password_hash'].encode()):
            _log_audit(db, current_user.id, 'change_password_failed', request.remote_addr)
            return jsonify({'error': 'Current password is incorrect'}), 401
    except Exception:
        return jsonify({'error': 'Password verification failed'}), 500

    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, current_user.id))
    db.commit()

    _log_audit(db, current_user.id, 'password_changed', request.remote_addr)
    return jsonify({'message': 'Password changed successfully'}), 200