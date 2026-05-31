import bcrypt
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from models import get_user_by_username, get_user_by_id, User
import os

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/pulsecheck.db')


@auth_bp.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    row = get_user_by_username(username, DATABASE_PATH)
    if not row:
        logger.warning(f'Login failed: unknown user {username}')
        return jsonify({'error': 'Invalid credentials'}), 401

    if not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        logger.warning(f'Login failed: bad password for {username}')
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(row['id'], row['username'], row['email'], row['role'])
    login_user(user, remember=True)
    logger.info(f'User {username} logged in successfully')
    return jsonify({'message': 'Login successful', 'user': {'id': user.id, 'username': user.username, 'role': user.role}}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f'User {username} logged out')
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    New user self-registration endpoint.
    Validates email format and password strength before creating account.
    """
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'All fields required'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters'}), 400

    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'Invalid email address'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    import sqlite3
    from models import get_db
    conn = get_db(DATABASE_PATH)
    try:
        existing = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        if existing:
            return jsonify({'error': 'Username or email already taken'}), 409

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, pw_hash)
        )
        conn.commit()
        logger.info(f'New user registered: {username}')
        return jsonify({'message': 'Account created successfully'}), 201
    finally:
        conn.close()


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role
    }), 200