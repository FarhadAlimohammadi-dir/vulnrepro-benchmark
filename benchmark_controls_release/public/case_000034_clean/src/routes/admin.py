import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.database import get_connection, log_audit

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


def _require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            log_audit(
                current_user.id if current_user.is_authenticated else None,
                'ADMIN_ACCESS_DENIED',
                f'Unauthorized admin access attempt from {request.remote_addr}',
                request.remote_addr
            )
            return jsonify({'error': 'Administrator access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/api/admin/users', methods=['GET'])
@login_required
@_require_admin
def list_users():
    """Admin-only: lists all users with full account details."""
    conn = get_connection()
    users = conn.execute(
        "SELECT id, username, email, is_admin, is_corporate, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({'users': [dict(u) for u in users]}), 200


@admin_bp.route('/api/admin/users/<int:user_id>/revoke-corporate', methods=['POST'])
@login_required
@_require_admin
def revoke_corporate(user_id):
    """Admin: revokes corporate access from a specific user account."""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    conn.execute("UPDATE users SET is_corporate = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'REVOKE_CORPORATE', f'Revoked corporate access for user {user_id}', request.remote_addr)
    return jsonify({'message': f'Corporate access revoked for user {user_id}'}), 200


@admin_bp.route('/api/admin/audit-log', methods=['GET'])
@login_required
@_require_admin
def get_audit_log():
    """Admin: returns recent audit log entries."""
    limit = min(int(request.args.get('limit', 50)), 200)
    conn = get_connection()
    logs = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return jsonify({'logs': [dict(l) for l in logs]}), 200


@admin_bp.route('/api/admin/stats', methods=['GET'])
@login_required
@_require_admin
def get_stats():
    """Admin dashboard: aggregate platform statistics."""
    conn = get_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    corporate_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_corporate = 1").fetchone()[0]
    total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    corporate_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE is_corporate = 1").fetchone()[0]
    conn.close()

    return jsonify({
        'total_users': total_users,
        'corporate_users': corporate_users,
        'total_docs': total_docs,
        'corporate_docs': corporate_docs,
    }), 200


@admin_bp.route('/api/admin/invitations', methods=['POST'])
@login_required
@_require_admin
def create_invitation():
    """Admin: generates an invitation token for a given email address."""
    import secrets
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()

    if not email:
        return jsonify({'error': 'Email required'}), 400

    token = secrets.token_urlsafe(32)
    conn = get_connection()
    conn.execute("INSERT INTO invitations (email, token) VALUES (?, ?)", (email, token))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'INVITATION_CREATED', f'Invitation created for {email}', request.remote_addr)
    return jsonify({'message': 'Invitation created', 'token': token}), 201