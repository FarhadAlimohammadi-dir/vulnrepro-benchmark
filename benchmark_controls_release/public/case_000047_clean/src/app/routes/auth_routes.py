import os
import json
import base64
import hmac
import hashlib
import time
import logging
import sqlite3
import bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _issue_jwt(user_id: int, username: str, role: str) -> str:
    """Issue a signed HS256 JWT for the given user."""
    secret = current_app.config['JWT_SECRET'].encode()

    header = {'alg': 'HS256', 'typ': 'JWT'}
    payload = {
        'sub': username,
        'uid': user_id,
        'role': role,
        'iat': int(time.time()),
        'exp': int(time.time()) + 3600,
        'iss': 'collabify-api'
    }

    h = _b64url_encode(json.dumps(header, separators=(',', ':')).encode())
    p = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode())
    signing_input = f"{h}.{p}".encode()
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    s = _b64url_encode(sig)

    return f"{h}.{p}.{s}"


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user credentials and return a signed JWT."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, email, password_hash, role, is_active FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or not user['is_active']:
            logger.info(f"Login attempt for unknown/inactive user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            logger.info(f"Failed login for user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        token = _issue_jwt(user['id'], user['username'], user['role'])

        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user['id'])
        )
        conn.execute(
            """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, timestamp)
               VALUES (?, 'LOGIN', 'user', ?, 'Successful login', ?, ?)""",
            (user['id'], user['id'], request.remote_addr, datetime.utcnow().isoformat())
        )
        conn.commit()

        logger.info(f"User {username} logged in successfully")
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        })
    finally:
        conn.close()


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh an existing valid token to extend its TTL."""
    from app.middleware.auth import verify_api_token

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Bearer token required'}), 401

    token = auth_header[len('Bearer '):]
    payload = verify_api_token(token)
    if not payload:
        return jsonify({'error': 'Invalid token'}), 401

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, role, is_active FROM users WHERE username = ?",
            (payload.get('sub'),)
        ).fetchone()

        if not user or not user['is_active']:
            return jsonify({'error': 'User not found or inactive'}), 401

        new_token = _issue_jwt(user['id'], user['username'], user['role'])
        return jsonify({'token': new_token})
    finally:
        conn.close()


@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    """Return information about the currently authenticated user."""
    from app.middleware.auth import verify_api_token

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Not authenticated'}), 401

    token = auth_header[len('Bearer '):]
    payload = verify_api_token(token)
    if not payload:
        return jsonify({'error': 'Invalid token'}), 401

    return jsonify({
        'sub': payload.get('sub'),
        'role': payload.get('role'),
        'uid': payload.get('uid')
    })