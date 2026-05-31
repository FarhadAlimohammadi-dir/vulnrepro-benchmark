import logging
import bcrypt
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from db import get_db
from models.user import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing credentials'}), 400

    db = get_db()
    row = db.execute(
        'SELECT * FROM users WHERE username = ?', (data['username'],)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not bcrypt.checkpw(data['password'].encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(row['id'], row['username'], row['email'], row['role'])
    login_user(user)

    db.execute(
        'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],)
    )
    db.commit()

    logger.info(f"User {user.username} logged in")
    return jsonify({'message': 'Logged in', 'user': user.to_dict()})


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logger.info(f"User {current_user.username} logged out")
    logout_user()
    return jsonify({'message': 'Logged out'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({'user': current_user.to_dict()})