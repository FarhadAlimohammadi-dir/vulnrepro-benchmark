import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.database import get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    user = User.get_by_credentials(email, password)
    if not user:
        logger.warning("Failed login attempt for email: %s from %s", email, request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401

    login_user(user)
    _record_audit(user.id, 'LOGIN', request.remote_addr, 'method=password')
    logger.info("User %s logged in from %s", user.email, request.remote_addr)
    return jsonify({'success': True, 'username': user.username, 'email': user.email})

@auth_bp.route('/register', methods=['POST'])
def register():
    import bcrypt
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not email or not username or not password:
        return jsonify({'error': 'All fields required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    existing = User.get_by_email(email)
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    conn = get_db()
    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
            (email, username, pw_hash)
        )
        conn.commit()
        logger.info("New user registered: %s", email)
        return jsonify({'success': True, 'message': 'Account created successfully'})
    except Exception as e:
        logger.error("Registration error: %s", e)
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        conn.close()

@auth_bp.route('/logout')
@login_required
def logout():
    logger.info("User %s logged out", current_user.email)
    logout_user()
    return redirect(url_for('auth.login_page'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Requires current password — properly validated."""
    import bcrypt
    data = request.get_json() or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not current_pw or not new_pw:
        return jsonify({'error': 'Both current and new password required'}), 400

    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (current_user.id,)
        ).fetchone()

        if not row or not row['password_hash']:
            return jsonify({'error': 'Password change not available for OAuth accounts'}), 400

        if not bcrypt.checkpw(current_pw.encode(), row['password_hash'].encode()):
            return jsonify({'error': 'Current password is incorrect'}), 401

        new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, current_user.id)
        )
        conn.commit()
        _record_audit(current_user.id, 'PASSWORD_CHANGE', request.remote_addr, '')
        return jsonify({'success': True})
    finally:
        conn.close()

def _record_audit(user_id, action, ip, metadata):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, ip_address, metadata) VALUES (?, ?, ?, ?)",
            (user_id, action, ip, metadata)
        )
        conn.commit()
    except Exception as e:
        logger.error("Audit log error: %s", e)
    finally:
        conn.close()