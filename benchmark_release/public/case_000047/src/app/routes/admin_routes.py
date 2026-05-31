import sqlite3
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import require_role

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@admin_bp.route('/users', methods=['GET'])
@require_role('admin')
def list_users():
    """
    Return all registered users. Restricted to platform administrators.
    Used by the admin dashboard for user management and access reviews.
    """
    conn = get_db()
    try:
        users = conn.execute(
            """SELECT id, username, email, role, created_at, last_login, is_active
               FROM users ORDER BY created_at ASC"""
        ).fetchall()

        return jsonify({
            'users': [dict(u) for u in users],
            'total': len(users)
        })
    finally:
        conn.close()


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@require_role('admin')
def update_user(user_id):
    """Update a user's role or active status. Admin-only operation."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    allowed_roles = ('admin', 'editor', 'viewer')
    updates = {}

    if 'role' in data:
        if data['role'] not in allowed_roles:
            return jsonify({'error': 'Invalid role'}), 400
        updates['role'] = data['role']

    if 'is_active' in data:
        updates['is_active'] = 1 if data['is_active'] else 0

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'User not found'}), 404

        set_clause = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)

        admin_user = request.token_payload.get('sub')
        conn.execute(
            """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, timestamp)
               VALUES ((SELECT id FROM users WHERE username=?), 'ADMIN_UPDATE', 'user', ?, ?, ?, ?)""",
            (admin_user, user_id, f"Updated: {updates}", request.remote_addr, datetime.utcnow().isoformat())
        )
        conn.commit()

        return jsonify({'message': 'User updated'})
    finally:
        conn.close()


@admin_bp.route('/audit', methods=['GET'])
@require_role('admin')
def get_audit_log():
    """Retrieve the platform audit log. Admin-only."""
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    action_filter = request.args.get('action', '')

    conn = get_db()
    try:
        if action_filter:
            entries = conn.execute(
                """SELECT a.*, u.username
                   FROM audit_log a LEFT JOIN users u ON a.user_id = u.id
                   WHERE a.action = ?
                   ORDER BY a.timestamp DESC LIMIT ? OFFSET ?""",
                (action_filter.upper(), limit, offset)
            ).fetchall()
        else:
            entries = conn.execute(
                """SELECT a.*, u.username
                   FROM audit_log a LEFT JOIN users u ON a.user_id = u.id
                   ORDER BY a.timestamp DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()

        return jsonify({
            'entries': [dict(e) for e in entries],
            'limit': limit,
            'offset': offset
        })
    finally:
        conn.close()


@admin_bp.route('/stats', methods=['GET'])
@require_role('admin')
def get_stats():
    """Return platform-wide statistics for the admin dashboard."""
    conn = get_db()
    try:
        total_users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()['cnt']
        active_users = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE is_active = 1"
        ).fetchone()['cnt']
        total_docs = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()['cnt']
        total_comments = conn.execute("SELECT COUNT(*) as cnt FROM comments").fetchone()['cnt']
        recent_logins = conn.execute(
            """SELECT COUNT(*) as cnt FROM audit_log
               WHERE action = 'LOGIN' AND timestamp > datetime('now', '-7 days')"""
        ).fetchone()['cnt']

        return jsonify({
            'users': {'total': total_users, 'active': active_users},
            'documents': {'total': total_docs},
            'comments': {'total': total_comments},
            'activity': {'logins_last_7d': recent_logins}
        })
    finally:
        conn.close()


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@require_role('admin')
def deactivate_user(user_id):
    """Deactivate a user account to prevent further logins."""
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        admin_sub = request.token_payload.get('sub')
        if user['username'] == admin_sub:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400

        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.execute(
            """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, timestamp)
               VALUES ((SELECT id FROM users WHERE username=?), 'DEACTIVATE', 'user', ?, ?, ?, ?)""",
            (admin_sub, user_id, f"Deactivated user: {user['username']}", request.remote_addr,
             datetime.utcnow().isoformat())
        )
        conn.commit()

        return jsonify({'message': f"User {user['username']} deactivated"})
    finally:
        conn.close()