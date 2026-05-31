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


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required'}), 400
    if len(username) > 40 or not username.replace('_', '').replace('-', '').isalnum():
        return jsonify({'error': 'Invalid username'}), 400
    if '@' not in email or len(email) > 254:
        return jsonify({'error': 'Invalid email address'}), 400
    if len(password) < 12:
        return jsonify({'error': 'Password must be at least 12 characters'}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (username, email)
    ).fetchone()
    if existing:
        return jsonify({'error': 'Account already exists'}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'user')",
        (username, email, pw_hash)
    )
    user_id = cur.lastrowid
    db.execute(
        "INSERT INTO audit_log (user_id, action, target_type, details, ip_address) VALUES (?,?,?,?,?)",
        (user_id, 'register', 'user', f'User {username} registered', request.remote_addr)
    )
    db.commit()

    user_obj = User(user_id, username, email, 'user')
    login_user(user_obj)
    return jsonify({'message': 'Registration successful', 'user': {'id': user_id, 'username': username, 'role': 'user'}}), 201


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
