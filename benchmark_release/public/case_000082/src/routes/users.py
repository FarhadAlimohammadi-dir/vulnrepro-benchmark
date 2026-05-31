import logging
from flask import Blueprint, request, jsonify, session
from models.database import get_db

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__)


@users_bp.route('/search', methods=['GET'])
def search_users():
    """
    Search users by username or email prefix.
    Returns limited fields - no password hashes exposed.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    if len(query) > 64:
        return jsonify({'error': 'Query too long'}), 400

    db = get_db()
    try:
        # Use parameterized query - safe from injection
        rows = db.execute(
            "SELECT id, username, email, role FROM users "
            "WHERE (username LIKE ? OR email LIKE ?) AND is_active = 1 LIMIT 20",
            (f"{query}%", f"{query}%")
        ).fetchall()
        return jsonify({'users': [dict(r) for r in rows]}), 200
    finally:
        db.close()


@users_bp.route('/<int:target_user_id>', methods=['GET'])
def get_user(target_user_id):
    """Fetch a user profile. Admins see all users, members see only themselves."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    role = session.get('role')
    if role != 'admin' and user_id != target_user_id:
        return jsonify({'error': 'Access denied'}), 403

    db = get_db()
    try:
        row = db.execute(
            "SELECT id, username, email, role, created_at, last_login, is_active "
            "FROM users WHERE id = ?",
            (target_user_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(dict(row)), 200
    finally:
        db.close()


@users_bp.route('/<int:target_user_id>/activity', methods=['GET'])
def get_user_activity(target_user_id):
    """Return recent audit log entries for a user. Admin only."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    role = session.get('role')
    if role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    db = get_db()
    try:
        rows = db.execute(
            "SELECT action, resource_type, resource_id, ip_address, created_at "
            "FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (target_user_id,)
        ).fetchall()
        return jsonify({'activity': [dict(r) for r in rows]}), 200
    finally:
        db.close()


@users_bp.route('/<int:target_user_id>/deactivate', methods=['POST'])
def deactivate_user(target_user_id):
    """Deactivate a user account. Admin only."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    role = session.get('role')
    if role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    if target_user_id == user_id:
        return jsonify({'error': 'Cannot deactivate your own account'}), 400

    db = get_db()
    try:
        db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (target_user_id,)
        )
        db.commit()
    finally:
        db.close()

    logger.info(f"Admin {user_id} deactivated user {target_user_id}")
    return jsonify({'message': 'User deactivated'}), 200