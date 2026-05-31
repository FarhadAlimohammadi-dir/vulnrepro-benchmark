import logging
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.database import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            logger.warning("Unauthorized admin access attempt by user %s", getattr(current_user, 'username', 'anonymous'))
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def get_stats():
    """System statistics for admin dashboard."""
    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    audit_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    public_doc_count = conn.execute("SELECT COUNT(*) FROM documents WHERE is_public=1").fetchone()[0]
    conn.close()

    return jsonify({
        'users': user_count,
        'documents': doc_count,
        'public_documents': public_doc_count,
        'audit_entries': audit_count,
    })


@admin_bp.route('/users', methods=['GET'])
@login_required
@require_admin
def list_users():
    """List all users (admin only)."""
    conn = get_db()
    rows = conn.execute("SELECT id, username, email, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    users = [dict(r) for r in rows]
    return jsonify({'users': users})


@admin_bp.route('/audit-log', methods=['GET'])
@login_required
@require_admin
def get_audit_log():
    """Retrieve recent audit log entries."""
    limit = min(int(request.args.get('limit', 50)), 200)
    conn = get_db()
    rows = conn.execute(
        """SELECT al.*, u.username FROM audit_log al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.created_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return jsonify({'entries': [dict(r) for r in rows], 'count': len(rows)})


@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@login_required
@require_admin
def update_user_role(user_id):
    """Update a user's role."""
    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '')
    if new_role not in ('user', 'admin'):
        return jsonify({'error': 'Invalid role. Must be user or admin'}), 400

    conn = get_db()
    result = conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        return jsonify({'error': 'User not found'}), 404

    logger.info("Admin %s changed role of user %d to %s", current_user.username, user_id, new_role)
    return jsonify({'message': f'Role updated to {new_role}'})