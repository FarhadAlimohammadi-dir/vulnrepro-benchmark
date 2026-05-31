import logging
import hashlib
import os
from flask import Blueprint, request, jsonify, session
import bcrypt
from db import get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    db = get_db()
    user = db.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not user:
        logger.warning("Login attempt for unknown user: %s", username)
        return jsonify({'error': 'invalid credentials'}), 401

    pw_bytes = password.encode('utf-8')
    stored_hash = user['password_hash'].encode('utf-8')

    if not bcrypt.checkpw(pw_bytes, stored_hash):
        logger.warning("Failed login for user: %s", username)
        return jsonify({'error': 'invalid credentials'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    logger.info("Successful login: %s (role=%s)", username, user['role'])
    return jsonify({
        'status': 'ok',
        'username': user['username'],
        'role': user['role']
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    username = session.get('username', 'anonymous')
    session.clear()
    logger.info("User logged out: %s", username)
    return jsonify({'status': 'ok'})


@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    if 'user_id' not in session:
        return jsonify({'error': 'not authenticated'}), 401
    return jsonify({
        'user_id': session['user_id'],
        'username': session['username'],
        'role': session['role']
    })