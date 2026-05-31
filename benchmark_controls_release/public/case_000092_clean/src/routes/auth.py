import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from models.db import get_user_by_username, get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('reports.dashboard'))
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = get_user_by_username(username)
    if not user or not user.check_password(password):
        logger.warning(f"Failed login attempt for username: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401

    login_user(user, remember=False)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
            (user.id, 'login', 'session', 'User authenticated', request.remote_addr)
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(f"User {username} logged in from {request.remote_addr}")
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role
        }
    })


@auth_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out")
    return jsonify({'success': True})


@auth_bp.route('/auth/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role
    })


@auth_bp.route('/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Allow users to update their own password."""
    data = request.get_json() or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not current_pw or not new_pw:
        return jsonify({'error': 'Both current and new password required'}), 400

    if not current_user.check_password(current_pw):
        return jsonify({'error': 'Current password is incorrect'}), 403

    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    from models.db import User
    new_hash = User.hash_password(new_pw)
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, current_user.id)
        )
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
            (current_user.id, 'password_change', 'user', 'Password updated', request.remote_addr)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True, 'message': 'Password updated successfully'})