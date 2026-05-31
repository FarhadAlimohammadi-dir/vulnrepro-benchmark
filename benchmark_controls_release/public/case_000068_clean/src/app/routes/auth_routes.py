import bcrypt
import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from ..db import get_db
from ..models import User

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'username and password required'}), 400

    username = data['username'].strip()
    password = data['password']

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
    finally:
        db.close()

    if row is None:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(row['id'], row['username'], row['email'], row['role'])
    login_user(user)

    logger.info(f"User {username} logged in from {request.remote_addr}")

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict()
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out")
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['username', 'email', 'password']
    for field in required:
        if field not in data or not data[field]:
            return jsonify({'error': f'{field} is required'}), 400

    username = data['username'].strip()
    email = data['email'].strip().lower()
    password = data['password']

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters'}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = get_db()
    try:
        db.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (username, email, pw_hash, 'editor')
        )
        db.commit()
    except Exception as e:
        db.close()
        if 'UNIQUE' in str(e):
            return jsonify({'error': 'Username or email already exists'}), 409
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        db.close()

    return jsonify({'message': 'Registration successful'}), 201


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({'user': current_user.to_dict()}), 200


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({'error': 'current_password and new_password required'}), 400

    current_password = data['current_password']
    new_password = data['new_password']

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM users WHERE id = ?', (current_user.id,)
        ).fetchone()

        if not bcrypt.checkpw(current_password.encode(), row['password_hash'].encode()):
            return jsonify({'error': 'Current password is incorrect'}), 401

        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        db.execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            (new_hash, current_user.id)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({'message': 'Password updated successfully'}), 200