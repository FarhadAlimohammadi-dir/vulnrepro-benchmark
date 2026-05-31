import logging
from flask import Blueprint, request, jsonify, session
import bcrypt
import database

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = database.query_db(
        "SELECT id, username, email, password_hash, role FROM users WHERE username = ?",
        (username,), one=True
    )

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    database.execute_db(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
        (user['id'],)
    )

    database.execute_db(
        "INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)",
        (user['id'], 'login', 'auth', request.remote_addr)
    )

    logger.info(f"User {username} logged in from {request.remote_addr}")
    return jsonify({
        "message": "Login successful",
        "user": {"id": user['id'], "username": user['username'], "role": user['role']}
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    user_id = session.get('user_id')
    if user_id:
        database.execute_db(
            "INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, 'logout', 'auth', request.remote_addr)
        )
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({"error": "All fields required"}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({"error": "Username must be 3-32 characters"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if '@' not in email:
        return jsonify({"error": "Invalid email format"}), 400

    existing = database.query_db(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (username, email), one=True
    )
    if existing:
        return jsonify({"error": "Username or email already taken"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = database.execute_db(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (username, email, pw_hash, 'analyst')
    )

    logger.info(f"New user registered: {username}")
    return jsonify({"message": "Account created successfully", "user_id": user_id}), 201


@auth_bp.route('/me', methods=['GET'])
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = database.query_db(
        "SELECT id, username, email, role, created_at, last_login FROM users WHERE id = ?",
        (user_id,), one=True
    )
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(dict(user))