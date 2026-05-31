import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing credentials'}), 400

    username = data['username'].strip()
    password = data['password']

    user = User.verify_password(username, password)
    if not user:
        logger.warning("Failed login attempt for username: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    login_user(user, remember=True)
    logger.info("User %s logged in", username)

    db = get_db()
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, ip_address) VALUES (?, ?, ?, ?)',
        (user.id, 'login', 'session', request.remote_addr)
    )
    db.commit()

    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logger.info("User %s logged out", current_user.username)
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role
    })


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    required = ['username', 'email', 'password']
    if not data or not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    username = data['username'].strip()
    email = data['email'].strip().lower()
    password = data['password']

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters'}), 400

    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = get_db()
    try:
        db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, 'user')
        )
        db.commit()
        logger.info("New user registered: %s", username)
        return jsonify({'message': 'Account created successfully'}), 201
    except Exception as e:
        logger.error("Registration error: %s", str(e))
        return jsonify({'error': 'Username or email already taken'}), 409


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({'error': 'Missing fields'}), 400

    import bcrypt
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()

    if not bcrypt.checkpw(data['current_password'].encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Current password is incorrect'}), 401

    new_hash = bcrypt.hashpw(data['new_password'].encode(), bcrypt.gensalt()).decode()
    db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, current_user.id))
    db.commit()

    return jsonify({'message': 'Password updated successfully'})