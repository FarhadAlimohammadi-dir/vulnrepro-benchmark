import bcrypt
import logging
from flask import Blueprint, request, jsonify, session, render_template
from flask_login import login_user, logout_user, login_required, current_user
from ..database import get_db
from ..models import User

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing credentials'}), 400

    username = data['username'].strip()
    password = data['password']

    db = get_db()
    row = db.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()

    if not row:
        logger.warning(f'Failed login attempt for unknown user: {username}')
        return jsonify({'error': 'Invalid credentials'}), 401

    stored_hash = row['password_hash'].encode()
    if not bcrypt.checkpw(password.encode(), stored_hash):
        logger.warning(f'Failed login attempt for user: {username}')
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(row['id'], row['username'], row['email'], row['role'])
    login_user(user)

    db.execute(
        'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
        (row['id'],)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (row['id'], 'LOGIN', 'user', row['id'], request.remote_addr)
    )
    db.commit()

    logger.info(f'User {username} logged in successfully')
    return jsonify({'message': 'Login successful', 'user': user.to_dict()})


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    db = get_db()
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'LOGOUT', 'user', current_user.id, request.remote_addr)
    )
    db.commit()
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify(current_user.to_dict())


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    row = db.execute(
        'SELECT password_hash FROM users WHERE id = ?', (current_user.id,)
    ).fetchone()

    if not bcrypt.checkpw(data['current_password'].encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Current password is incorrect'}), 403

    new_password = data['new_password']
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (new_hash, current_user.id)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'PASSWORD_CHANGE', 'user', current_user.id, request.remote_addr)
    )
    db.commit()

    return jsonify({'message': 'Password updated successfully'})