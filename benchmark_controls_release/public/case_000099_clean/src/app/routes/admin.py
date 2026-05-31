import logging
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def stats():
    db = get_db()
    user_count = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()['cnt']
    monitor_count = db.execute('SELECT COUNT(*) as cnt FROM monitors').fetchone()['cnt']
    check_count = db.execute('SELECT COUNT(*) as cnt FROM check_results').fetchone()['cnt']
    recent_checks = db.execute(
        'SELECT COUNT(*) as cnt FROM check_results WHERE checked_at > datetime("now", "-1 hour")'
    ).fetchone()['cnt']

    return jsonify({
        'users': user_count,
        'monitors': monitor_count,
        'total_checks': check_count,
        'checks_last_hour': recent_checks,
    })


@admin_bp.route('/users', methods=['GET'])
@login_required
@require_admin
def list_users():
    db = get_db()
    users = db.execute(
        'SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC'
    ).fetchall()
    return jsonify({'users': [dict(u) for u in users]})


@admin_bp.route('/audit', methods=['GET'])
@login_required
@require_admin
def audit_log():
    limit = min(int(request.args.get('limit', 50)), 500)
    db = get_db()
    logs = db.execute(
        '''SELECT a.*, u.username FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.created_at DESC LIMIT ?''',
        (limit,)
    ).fetchall()
    return jsonify({'logs': [dict(l) for l in logs]})


@admin_bp.route('/monitors/all', methods=['GET'])
@login_required
@require_admin
def all_monitors():
    db = get_db()
    monitors = db.execute(
        '''SELECT m.*, u.username FROM monitors m
           JOIN users u ON m.user_id = u.id
           ORDER BY m.created_at DESC'''
    ).fetchall()
    return jsonify({'monitors': [dict(m) for m in monitors]})