import bcrypt
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_user, logout_user, current_user
from ..database import get_db
from ..models import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and establish session."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    db = get_db()
    row = db.execute(
        'SELECT * FROM users WHERE username = ? AND is_active = 1',
        (username,)
    ).fetchone()
    db.close()

    if not row:
        logger.info("Failed login attempt for username: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    if not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        logger.info("Failed login attempt for username: %s (bad password)", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
    login_user(user, remember=False)

    db = get_db()
    db.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],))
    db.commit()
    db.close()

    logger.info("Successful login for user: %s (role: %s)", username, row['role'])
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
def logout():
    """Terminate user session."""
    username = getattr(current_user, 'username', 'anonymous')
    logout_user()
    logger.info("User logged out: %s", username)
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new member account (non-admin only via this endpoint)."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'All fields required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db = get_db()
    try:
        db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, 'member')
        )
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({'error': 'Username or email already exists'}), 409
    finally:
        db.close()

    logger.info("New user registered: %s", username)
    return jsonify({'message': 'Registration successful'}), 201


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh session for currently authenticated user."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role,
        }
    })