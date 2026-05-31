import logging
from flask import Blueprint, request, jsonify, session, current_app
from models.db import get_db
from routes.auth import require_auth

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

INTERNAL_ADMIN_IDS = {1}  # Only alice is platform admin for demo


def require_platform_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id or user_id not in INTERNAL_ADMIN_IDS:
            return jsonify({'error': 'Platform admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@require_auth
@require_platform_admin
def list_all_users():
    """Platform admin: list all registered users."""
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        rows = conn.execute(
            "SELECT id, username, email, display_name, created_at, is_active FROM users ORDER BY id"
        ).fetchall()
        return jsonify({'users': [dict(r) for r in rows]})
    finally:
        conn.close()


@admin_bp.route('/users/<int:uid>/deactivate', methods=['POST'])
@require_auth
@require_platform_admin
def deactivate_user(uid):
    """Platform admin: deactivate a user account."""
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot deactivate your own account'}), 400

    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        result = conn.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (uid,)
        )
        if result.rowcount == 0:
            return jsonify({'error': 'User not found'}), 404
        conn.commit()
        logger.info(f"Platform admin deactivated user {uid}")
        return jsonify({'message': 'User deactivated'})
    finally:
        conn.close()


@admin_bp.route('/stats', methods=['GET'])
@require_auth
@require_platform_admin
def platform_stats():
    """Platform admin: aggregate platform statistics."""
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        stats = {
            'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'total_orgs': conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0],
            'total_projects': conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            'total_service_accounts': conn.execute("SELECT COUNT(*) FROM service_accounts").fetchone()[0],
        }
        return jsonify({'stats': stats})
    finally:
        conn.close()