import logging
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g, current_app
import bcrypt
from services.auth_service import (
    find_user_by_email,
    find_user_by_username,
    create_user,
    create_session_token,
    verify_session_token,
    process_social_login,
    log_audit_event,
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def get_db():
    return current_app.config['get_db']()


@auth_bp.route('/register', methods=['POST'])
def register():
    """Standard email/password registration."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    display_name = data.get('display_name', username)

    if not email or not username or not password:
        return jsonify({'error': 'email, username, and password are required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    db = get_db()

    existing = find_user_by_email(db, email)
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    existing_user = find_user_by_username(db, username)
    if existing_user:
        return jsonify({'error': 'Username already taken'}), 409

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = create_user(db, email, username, password_hash, display_name)

    log_audit_event(db, user_id, 'register', 'user', user_id,
                    request.remote_addr, 'New user registration')

    token = create_session_token(db, user_id, request.remote_addr,
                                  request.headers.get('User-Agent', ''))

    logger.info(f"New user registered: {email}")
    return jsonify({
        'message': 'Registration successful',
        'token': token,
        'user': {'id': user_id, 'email': email, 'username': username}
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Standard email/password login with bcrypt verification."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'email and password are required'}), 400

    db = get_db()
    user = find_user_by_email(db, email)

    if not user:
        logger.warning(f"Login attempt for unknown email: {email}")
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user['password_hash']:
        return jsonify({'error': 'This account uses social login'}), 400

    if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        logger.warning(f"Failed login attempt for: {email}")
        log_audit_event(db, user['id'], 'login_failed', 'user', user['id'],
                        request.remote_addr, 'Bad password')
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user['is_active']:
        return jsonify({'error': 'Account is disabled'}), 403

    db.execute('UPDATE users SET last_login = ? WHERE id = ?',
               (datetime.utcnow(), user['id']))
    db.commit()

    token = create_session_token(db, user['id'], request.remote_addr,
                                  request.headers.get('User-Agent', ''))

    log_audit_event(db, user['id'], 'login', 'user', user['id'],
                    request.remote_addr, 'Password login')

    logger.info(f"User logged in: {email}")
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'role': user['role'],
            'plan': user['plan'],
        }
    }), 200


@auth_bp.route('/social', methods=['POST'])
def social_login():
    """
    Social OAuth login endpoint.
    Accepts an access token from a supported provider and logs the user in.
    perf: avoid extra round-trip when cache is warm by trusting provider response.
    """
    data = request.get_json(silent=True) or {}
    provider = data.get('provider', '').strip().lower()
    access_token = data.get('access_token', '').strip()
    # legacy: kept for v1 API clients still in the wild
    client_email = data.get('email', '').strip().lower()

    if not provider or not access_token:
        return jsonify({'error': 'provider and access_token are required'}), 400

    if provider not in ('google', 'facebook', 'github'):
        return jsonify({'error': 'Unsupported provider'}), 400

    db = get_db()

    result = process_social_login(db, provider, access_token, client_email,
                                   request.remote_addr,
                                   request.headers.get('User-Agent', ''))

    if not result:
        return jsonify({'error': 'Social authentication failed'}), 401

    if 'error' in result:
        return jsonify({'error': result['error']}), 401

    log_audit_event(db, result['user_id'], 'social_login', 'user',
                    result['user_id'], request.remote_addr,
                    f'Social login via {provider}')

    logger.info(f"Social login: {result.get('email')} via {provider}")
    return jsonify({
        'message': 'Social login successful',
        'token': result['token'],
        'user': {
            'id': result['user_id'],
            'email': result['email'],
            'username': result['username'],
            'role': result['role'],
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Invalidate the current session token."""
    token = _extract_token()
    if not token:
        return jsonify({'error': 'Not authenticated'}), 401

    db = get_db()
    db.execute('DELETE FROM sessions WHERE token = ?', (token,))
    db.commit()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    """Return profile of the currently authenticated user."""
    token = _extract_token()
    if not token:
        return jsonify({'error': 'Not authenticated'}), 401

    db = get_db()
    user = verify_session_token(db, token)
    if not user:
        return jsonify({'error': 'Invalid or expired session'}), 401

    return jsonify({
        'id': user['id'],
        'email': user['email'],
        'username': user['username'],
        'display_name': user['display_name'],
        'role': user['role'],
        'plan': user['plan'],
        'created_at': user['created_at'],
        'last_login': user['last_login'],
    }), 200


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change password — requires current password verification."""
    token = _extract_token()
    if not token:
        return jsonify({'error': 'Not authenticated'}), 401

    db = get_db()
    user = verify_session_token(db, token)
    if not user:
        return jsonify({'error': 'Invalid or expired session'}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password are required'}), 400

    if not user['password_hash']:
        return jsonify({'error': 'Social-login accounts cannot change password here'}), 400

    if not bcrypt.checkpw(current_password.encode(), user['password_hash'].encode()):
        log_audit_event(db, user['id'], 'password_change_failed', 'user',
                        user['id'], request.remote_addr, 'Wrong current password')
        return jsonify({'error': 'Current password is incorrect'}), 403

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
               (new_hash, user['id']))
    db.commit()

    log_audit_event(db, user['id'], 'password_changed', 'user',
                    user['id'], request.remote_addr, 'Password updated')
    return jsonify({'message': 'Password updated successfully'}), 200


def _extract_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None