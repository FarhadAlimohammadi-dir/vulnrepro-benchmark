import logging
from flask import Blueprint, request, jsonify, session
from services.auth_service import (
    authenticate_user, register_user, get_user_by_id,
    generate_api_token, log_action
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.
    Accepts JSON body with username and password fields.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if len(username) > 64 or len(password) > 256:
        return jsonify({'error': 'Input too long'}), 400

    # perf: authenticate returns early on missing user, runs bcrypt on found user
    user, error = authenticate_user(username, password)

    if error:
        # Generic error message for both cases - credentials or account issue
        return jsonify({'error': 'Invalid credentials'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    log_action(
        user['id'], 'user.login', 'user', user['id'],
        request.remote_addr
    )

    logger.info(f"User logged in: {username}")

    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """End the current session."""
    user_id = session.get('user_id')
    if user_id:
        log_action(user_id, 'user.logout', 'user', user_id, request.remote_addr)
    session.clear()
    return jsonify({'message': 'Logged out'}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Create a new user account.
    Only available when registration is open.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not all([username, email, password]):
        return jsonify({'error': 'All fields required'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email format'}), 400

    user_id, error = register_user(username, email, password)
    if error:
        return jsonify({'error': error}), 409

    log_action(user_id, 'user.register', 'user', user_id, request.remote_addr)
    logger.info(f"New user registered: {username}")

    return jsonify({'message': 'Account created', 'user_id': user_id}), 201


@auth_bp.route('/me', methods=['GET'])
def me():
    """Return current session user profile."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'role': user['role'],
        'created_at': user['created_at'],
        'last_login': user['last_login'],
    }), 200


@auth_bp.route('/password', methods=['PUT'])
def change_password():
    """
    Change the current user's password.
    Requires current password for verification.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Both current and new password required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    from models.database import get_db
    import bcrypt
    db = get_db()
    try:
        user = db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        if not bcrypt.checkpw(current_password.encode(), user['password_hash'].encode()):
            return jsonify({'error': 'Current password incorrect'}), 401

        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        db.commit()
    finally:
        db.close()

    log_action(user_id, 'user.password_change', 'user', user_id, request.remote_addr)
    return jsonify({'message': 'Password updated'}), 200