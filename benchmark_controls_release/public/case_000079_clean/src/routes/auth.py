import os
import sqlite3
import secrets
import bcrypt
import logging
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT * FROM users WHERE username=? AND active=1', (username,)
        ).fetchone()

        if not user or not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            logger.warning(f"Failed login attempt for username: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=8)
        conn.execute(
            'INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
            (user['id'], token, expires.isoformat())
        )
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
            (user['id'], 'LOGIN', 'auth', 'Successful login', request.remote_addr)
        )
        conn.commit()

        session['user_id'] = user['id']
        session['token'] = token

        logger.info(f"User {username} logged in successfully")
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'department': user['department']
            },
            'expires_at': expires.isoformat()
        })
    finally:
        conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        conn = get_db()
        try:
            conn.execute('DELETE FROM sessions WHERE token=?', (token,))
            conn.commit()
        finally:
            conn.close()
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'error': 'Token required'}), 401

    conn = get_db()
    try:
        sess = conn.execute(
            'SELECT s.*, u.username, u.role FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=?',
            (token,)
        ).fetchone()

        if not sess:
            return jsonify({'error': 'Invalid token'}), 401

        new_token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=8)
        conn.execute('DELETE FROM sessions WHERE token=?', (token,))
        conn.execute(
            'INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
            (sess['user_id'], new_token, expires.isoformat())
        )
        conn.commit()
        return jsonify({'token': new_token, 'expires_at': expires.isoformat()})
    finally:
        conn.close()