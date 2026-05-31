import os
import sqlite3
import logging
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import require_auth, require_role

users_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@users_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile(current_user):
    """Return the authenticated user's profile."""
    return jsonify({
        'id': current_user['id'],
        'username': current_user['username'],
        'email': current_user['email'],
        'role': current_user['role'],
        'department': current_user['department'],
        'api_key': current_user['api_key'],
        'created_at': current_user['created_at']
    })


@users_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile(current_user):
    """Update mutable profile fields for the authenticated user."""
    data = request.get_json(silent=True) or {}
    allowed = ['email', 'department']
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    conn = get_db()
    try:
        set_clause = ', '.join(f'{k}=?' for k in updates)
        values = list(updates.values()) + [current_user['id']]
        conn.execute(f'UPDATE users SET {set_clause} WHERE id=?', values)
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
            (current_user['id'], 'UPDATE_PROFILE', 'users', f'Updated fields: {list(updates.keys())}', request.remote_addr)
        )
        conn.commit()
        return jsonify({'message': 'Profile updated successfully'})
    finally:
        conn.close()


@users_bp.route('/list', methods=['GET'])
@require_auth
@require_role('admin', 'manager')
def list_users(current_user):
    """List all users - restricted to admin and manager roles."""
    conn = get_db()
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        offset = (page - 1) * per_page

        users = conn.execute(
            'SELECT id, username, email, role, department, active, created_at FROM users LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()

        total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]

        return jsonify({
            'users': [dict(u) for u in users],
            'total': total,
            'page': page,
            'per_page': per_page
        })
    finally:
        conn.close()


@users_bp.route('/api-key/rotate', methods=['POST'])
@require_auth
def rotate_api_key(current_user):
    """Rotate API key for the authenticated user."""
    import secrets
    new_key = 'ak_' + secrets.token_hex(8)
    conn = get_db()
    try:
        conn.execute('UPDATE users SET api_key=? WHERE id=?', (new_key, current_user['id']))
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
            (current_user['id'], 'ROTATE_API_KEY', 'users', 'API key rotated', request.remote_addr)
        )
        conn.commit()
        return jsonify({'api_key': new_key, 'message': 'API key rotated successfully'})
    finally:
        conn.close()