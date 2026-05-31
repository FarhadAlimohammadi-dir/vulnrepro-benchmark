import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import get_db
from functools import wraps

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    conn = get_db()
    rows = conn.execute(
        'SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return jsonify({'users': [dict(r) for r in rows]})


@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@login_required
@admin_required
def update_user_role(user_id):
    data = request.get_json()
    new_role = data.get('role', '')
    if new_role not in ('user', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    conn = get_db()
    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()

    logger.info("Admin %s changed role of user %d to %s", current_user.username, user_id, new_role)
    return jsonify({'message': 'Role updated'})


@admin_bp.route('/audit', methods=['GET'])
@login_required
@admin_required
def audit_logs():
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)
    offset = (page - 1) * per_page

    conn = get_db()
    rows = conn.execute(
        '''SELECT al.id, al.action, al.resource, al.ip_address, al.created_at,
                  u.username
           FROM audit_logs al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.created_at DESC
           LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()

    total = conn.execute('SELECT COUNT(*) as cnt FROM audit_logs').fetchone()['cnt']
    conn.close()

    return jsonify({
        'logs': [dict(r) for r in rows],
        'page': page,
        'per_page': per_page,
        'total': total
    })


@admin_bp.route('/reports/all', methods=['GET'])
@login_required
@admin_required
def all_reports():
    conn = get_db()
    rows = conn.execute(
        '''SELECT r.id, r.title, r.status, r.created_at, u.username as owner
           FROM reports r JOIN users u ON r.owner_id = u.id
           ORDER BY r.created_at DESC'''
    ).fetchall()
    conn.close()
    return jsonify({'reports': [dict(r) for r in rows]})