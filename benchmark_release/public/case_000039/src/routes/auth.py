import logging
from flask import Blueprint, request, jsonify, session, current_app
from models.db import get_db, check_password

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        user = conn.execute(
            "SELECT id, username, email, display_name, is_active FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()


def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        user = conn.execute(
            "SELECT id, username, email, display_name, password_hash, is_active FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or not check_password(password, user['password_hash']):
            logger.warning(f"Failed login attempt for username: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        if not user['is_active']:
            return jsonify({'error': 'Account disabled'}), 403

        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True

        logger.info(f"User {username} logged in successfully")
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'display_name': user['display_name'],
            }
        })
    finally:
        conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
def me():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    # Remove sensitive fields
    user.pop('password_hash', None)
    return jsonify({'user': user})


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Allow authenticated users to update their own password."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not current_pw or not new_pw:
        return jsonify({'error': 'Both current and new password required'}), 400

    if len(new_pw) < 10:
        return jsonify({'error': 'Password must be at least 10 characters'}), 400

    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        user = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if not user or not check_password(current_pw, user['password_hash']):
            return jsonify({'error': 'Current password is incorrect'}), 403

        import bcrypt
        new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        conn.commit()
        logger.info(f"Password changed for user_id={user_id}")
        return jsonify({'message': 'Password updated successfully'})
    finally:
        conn.close()