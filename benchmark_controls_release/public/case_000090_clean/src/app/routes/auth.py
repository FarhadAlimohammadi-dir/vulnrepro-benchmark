import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from app.models import User, get_db
from app import login_manager

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user_row = User.get_by_username(username)
    if not user_row:
        logger.warning("Failed login attempt for unknown user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    pw_hash = user_row['password_hash'].encode()
    if not bcrypt.checkpw(password.encode(), pw_hash):
        logger.warning("Failed login attempt for user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    user_obj = User(user_row['id'], user_row['username'], user_row['email'], user_row['role'])
    login_user(user_obj)

    db = get_db()
    db.execute(
        "INSERT INTO audit_log (user_id, action, target_type, details, ip_address) VALUES (?,?,?,?,?)",
        (user_obj.id, 'login', 'session', f'User {username} logged in', request.remote_addr)
    )
    db.commit()

    logger.info("User %s logged in successfully", username)
    return jsonify({'message': 'Login successful', 'user': {'id': user_obj.id, 'username': user_obj.username, 'role': user_obj.role}}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info("User %s logged out", username)
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role
    }), 200


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update authenticated user's profile information."""
    data = request.get_json(silent=True) or {}

    allowed_fields = {'email', 'display_name'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    if 'email' in updates:
        email = updates['email']
        if '@' not in email or len(email) > 254:
            return jsonify({'error': 'Invalid email address'}), 400

    db = get_db()
    if 'email' in updates:
        db.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            (updates['email'], current_user.id)
        )

    db.execute(
        "INSERT INTO audit_log (user_id, action, target_type, target_id, details, ip_address) VALUES (?,?,?,?,?,?)",
        (current_user.id, 'update_profile', 'user', current_user.id, 'Profile updated', request.remote_addr)
    )
    db.commit()

    logger.info("User %s updated profile", current_user.username)
    return jsonify({'message': 'Profile updated successfully'}), 200