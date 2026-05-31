import logging
from flask import Blueprint, jsonify, redirect, url_for, g, request
from models.database import query_db, execute_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def require_admin(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('auth.login'))
        if g.user['role'] != 'admin':
            logger.warning(f'Non-admin access attempt by {g.user["username"]}')
            return jsonify({'error': 'Forbidden'}), 403
        return fn(*args, **kwargs)
    return wrapped


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    users = query_db(
        'SELECT id, username, email, role, full_name, created_at, last_login FROM users ORDER BY created_at DESC'
    )
    return jsonify([dict(u) for u in users])


@admin_bp.route('/users/<int:user_id>/role', methods=['PATCH'])
@require_admin
def update_user_role(user_id):
    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '')

    if new_role not in ('admin', 'member', 'viewer'):
        return jsonify({'error': 'Invalid role'}), 400

    user = query_db('SELECT * FROM users WHERE id=?', (user_id,), one=True)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    execute_db('UPDATE users SET role=? WHERE id=?', (new_role, user_id))
    execute_db(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)',
        (g.user['id'], 'admin.role_change', 'user', user_id,
         f'Changed {user["username"]} role to {new_role}', request.remote_addr)
    )
    return jsonify({'user_id': user_id, 'new_role': new_role})


@admin_bp.route('/stats', methods=['GET'])
@require_admin
def get_stats():
    stats = {
        'users': query_db('SELECT COUNT(*) as c FROM users', one=True)['c'],
        'projects': query_db('SELECT COUNT(*) as c FROM projects', one=True)['c'],
        'tasks': query_db('SELECT COUNT(*) as c FROM tasks', one=True)['c'],
        'open_tasks': query_db("SELECT COUNT(*) as c FROM tasks WHERE status != 'done'", one=True)['c'],
    }
    return jsonify(stats)