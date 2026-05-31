import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from models.database import get_user_by_username, get_db, hash_password

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = get_user_by_username(username)
    if not user:
        logger.warning("Failed login attempt for unknown user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    expected_hash = hash_password(password)
    if user.password_hash != expected_hash:
        logger.warning("Failed login attempt for user: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    login_user(user, remember=True)
    logger.info("User %s logged in successfully", username)

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
            (user.id, 'LOGIN', 'auth', request.remote_addr, f'User {username} logged in')
        )
        conn.commit()
    finally:
        conn.close()

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
    username = current_user.username
    logout_user()
    logger.info("User %s logged out", username)
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


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Both current and new password required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    expected_hash = hash_password(current_password)
    if current_user.password_hash != expected_hash:
        return jsonify({'error': 'Current password is incorrect'}), 401

    new_hash = hash_password(new_password)
    conn = get_db()
    try:
        conn.execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            (new_hash, current_user.id)
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("User %s changed their password", current_user.username)
    return jsonify({'message': 'Password updated successfully'})