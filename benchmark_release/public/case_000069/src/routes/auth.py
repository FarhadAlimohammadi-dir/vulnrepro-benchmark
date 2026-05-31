import logging
from flask import Blueprint, request, session, jsonify, redirect, url_for, render_template
from models.db import get_connection, verify_password

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, username, email, password_hash, role, plan FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or not verify_password(password, user['password_hash']):
            logger.warning(f"Failed login attempt for username: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user['id'],)
        )
        conn.execute(
            """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address)
               VALUES (?, 'user.login', 'user', ?, ?)""",
            (user['id'], user['id'], request.remote_addr)
        )
        conn.commit()

        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

        logger.info(f"User {username} logged in successfully")
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'plan': user['plan'],
            }
        }), 200

    finally:
        conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    user_id = session.get('user_id')
    if user_id:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address)
                   VALUES (?, 'user.logout', 'user', ?, ?)""",
                (user_id, user_id, request.remote_addr)
            )
            conn.commit()
        finally:
            conn.close()

    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200