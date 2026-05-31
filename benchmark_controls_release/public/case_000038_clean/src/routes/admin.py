import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models.database import get_db

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if not current_user.is_active:
            return jsonify({'error': 'Account inactive'}), 403
        if current_user.role != 'admin':
            logger.warning(f"Unauthorized admin access attempt by user_id={current_user.id}")
            return jsonify({'error': 'Insufficient permissions'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@login_required
@require_admin
def list_users():
    """Admin: list all platform users with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    offset = (page - 1) * per_page

    db = get_db()
    users = db.execute(
        """SELECT id, email, username, display_name, country, role,
                  account_status, created_at, last_login
           FROM users
           ORDER BY created_at DESC
           LIMIT ? OFFSET ?""",
        (per_page, offset)
    ).fetchall()

    total = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()['cnt']

    return jsonify({
        'users': [dict(u) for u in users],
        'total': total,
        'page': page,
        'per_page': per_page
    }), 200


@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@require_admin
def suspend_user(user_id):
    """Admin: suspend a user account."""
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot suspend your own account'}), 400

    db = get_db()
    db.execute("UPDATE users SET account_status = 'suspended' WHERE id = ?", (user_id,))
    db.commit()

    db.execute(
        "INSERT INTO audit_log (user_id, action, ip_address, details) VALUES (?, ?, ?, ?)",
        (current_user.id, 'admin_suspend_user', request.remote_addr, f'target_user_id={user_id}')
    )
    db.commit()

    return jsonify({'message': f'User {user_id} suspended'}), 200


@admin_bp.route('/users/<int:user_id>/activate', methods=['POST'])
@login_required
@require_admin
def activate_user(user_id):
    """Admin: reactivate a suspended user account."""
    db = get_db()
    db.execute("UPDATE users SET account_status = 'active' WHERE id = ?", (user_id,))
    db.commit()

    db.execute(
        "INSERT INTO audit_log (user_id, action, ip_address, details) VALUES (?, ?, ?, ?)",
        (current_user.id, 'admin_activate_user', request.remote_addr, f'target_user_id={user_id}')
    )
    db.commit()

    return jsonify({'message': f'User {user_id} activated'}), 200


@admin_bp.route('/audit-log', methods=['GET'])
@login_required
@require_admin
def get_audit_log():
    """Admin: retrieve platform audit log with optional filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    offset = (page - 1) * per_page
    action_filter = request.args.get('action')

    db = get_db()
    query = "SELECT * FROM audit_log"
    params = []
    if action_filter:
        query += " WHERE action = ?"
        params.append(action_filter)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [per_page, offset]

    logs = db.execute(query, params).fetchall()
    total = db.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()['cnt']

    return jsonify({
        'logs': [dict(l) for l in logs],
        'total': total,
        'page': page
    }), 200


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def platform_stats():
    """Admin: high-level platform statistics dashboard."""
    db = get_db()

    stats = {
        'total_users': db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c'],
        'active_users': db.execute("SELECT COUNT(*) as c FROM users WHERE account_status='active'").fetchone()['c'],
        'total_games': db.execute("SELECT COUNT(*) as c FROM games").fetchone()['c'],
        'total_orders': db.execute("SELECT COUNT(*) as c FROM orders").fetchone()['c'],
        'total_reviews': db.execute("SELECT COUNT(*) as c FROM reviews").fetchone()['c'],
        'library_entries': db.execute("SELECT COUNT(*) as c FROM user_library").fetchone()['c'],
    }

    return jsonify({'stats': stats}), 200
