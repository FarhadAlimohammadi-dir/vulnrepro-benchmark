import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..database import get_db

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({'error': 'Administrator access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@login_required
@require_admin
def list_users():
    db = get_db()
    rows = db.execute(
        'SELECT id, username, email, role, created_at, last_login FROM users ORDER BY created_at'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@require_admin
def update_user(user_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    allowed_roles = ('admin', 'member', 'viewer')
    role = data.get('role')
    if role and role not in allowed_roles:
        return jsonify({'error': 'Invalid role'}), 400

    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404

    new_role = role or row['role']
    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'ROLE_CHANGE', 'user', user_id, request.remote_addr)
    )
    db.commit()
    logger.info(f'Admin {current_user.username} updated role for user {user_id} to {new_role}')
    return jsonify({'message': 'User updated', 'user_id': user_id, 'role': new_role})


@admin_bp.route('/audit', methods=['GET'])
@login_required
@require_admin
def audit_log():
    db = get_db()
    limit = min(int(request.args.get('limit', 100)), 500)
    rows = db.execute(
        '''SELECT al.*, u.username FROM audit_log al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.created_at DESC LIMIT ?''',
        (limit,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def stats():
    db = get_db()
    user_count = db.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
    project_count = db.execute('SELECT COUNT(*) as c FROM projects').fetchone()['c']
    comment_count = db.execute('SELECT COUNT(*) as c FROM comments').fetchone()['c']
    widget_count = db.execute('SELECT COUNT(*) as c FROM widget_messages').fetchone()['c']

    return jsonify({
        'users': user_count,
        'projects': project_count,
        'comments': comment_count,
        'widget_messages': widget_count,
    })