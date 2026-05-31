import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app.database import get_db, check_password, hash_password
from app.models import User
import secrets

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.get_by_username(username)
    if not user:
        logger.warning("Login attempt for unknown user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
    conn.close()

    if not row or not check_password(password, row['password_hash']):
        logger.warning("Failed login for user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    login_user(user)
    logger.info("User %s logged in successfully", username)

    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (user_id, action, resource_type, ip_address) VALUES (?,?,?,?)",
        (user.id, 'login', 'session', request.remote_addr)
    )
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    logger.info("User %d logged out", user_id)
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'All fields required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters'}), 400

    existing = User.get_by_username(username)
    if existing:
        return jsonify({'error': 'Username already taken'}), 409

    existing_email = User.get_by_email(email)
    if existing_email:
        return jsonify({'error': 'Email already registered'}), 409

    pw_hash = hash_password(password)
    api_token = secrets.token_hex(24)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role, api_token) VALUES (?,?,?,?,?)",
            (username, email, pw_hash, 'user', api_token)
        )
        conn.commit()
        logger.info("New user registered: %s", username)
    except Exception as e:
        logger.error("Registration error: %s", str(e))
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        conn.close()

    return jsonify({'message': 'Registration successful'}), 201


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role,
    })


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not current_pw or not new_pw:
        return jsonify({'error': 'Both current and new password required'}), 400

    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (current_user.id,)).fetchone()
    conn.close()

    if not row or not check_password(current_pw, row['password_hash']):
        return jsonify({'error': 'Current password incorrect'}), 403

    new_hash = hash_password(new_pw)
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user.id))
    conn.commit()
    conn.close()

    logger.info("Password changed for user %d", current_user.id)
    return jsonify({'message': 'Password updated successfully'})