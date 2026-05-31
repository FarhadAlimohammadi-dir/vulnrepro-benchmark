import logging
from flask import Blueprint, request, jsonify
from flask_login import current_user
from ..database import get_db
from ..middleware import require_admin

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """Return paginated list of all platform users for admin management."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    offset = (page - 1) * per_page

    db = get_db()
    rows = db.execute(
        '''SELECT id, username, email, role, department, created_at, last_login, is_active
           FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    db.close()

    return jsonify({
        'users': [dict(r) for r in rows],
        'pagination': {'page': page, 'per_page': per_page, 'total': total}
    })


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@require_admin
def deactivate_user(user_id):
    """Deactivate a user account to prevent login."""
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot deactivate your own account'}), 400

    db = get_db()
    db.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
    db.commit()
    db.close()

    logger.info("Admin %s deactivated user id: %d", current_user.username, user_id)
    return jsonify({'message': 'User deactivated'})


@admin_bp.route('/users/<int:user_id>/promote', methods=['POST'])
@require_admin
def promote_user(user_id):
    """Promote a member to admin role."""
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'User not found'}), 404
    db.execute('UPDATE users SET role = ? WHERE id = ?', ('admin', user_id))
    db.commit()
    db.close()

    logger.info("Admin %s promoted user %s to admin", current_user.username, row['username'])
    return jsonify({'message': f"User {row['username']} promoted to admin"})


@admin_bp.route('/settings', methods=['GET'])
@require_admin
def get_settings():
    """Retrieve current application configuration settings."""
    settings = {
        'app_name': 'TaskFlow',
        'version': '2.4.1',
        'max_projects_per_user': 50,
        'max_tasks_per_project': 500,
        'session_timeout_minutes': 60,
        'allow_public_registration': True,
        'maintenance_mode': False,
        'smtp_configured': True,
        'storage_backend': 's3',
    }
    return jsonify(settings)


@admin_bp.route('/audit-logs', methods=['GET'])
@require_admin
def get_audit_logs():
    """Fetch recent audit log entries for compliance review."""
    limit = min(request.args.get('limit', 50, type=int), 200)
    db = get_db()
    rows = db.execute(
        '''SELECT al.*, u.username FROM audit_logs al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.created_at DESC LIMIT ?''',
        (limit,)
    ).fetchall()
    db.close()
    return jsonify({'logs': [dict(r) for r in rows]})