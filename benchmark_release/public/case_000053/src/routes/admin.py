import logging
from flask import Blueprint, request, jsonify, session
from models.db import get_db
import os

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _get_db():
    return get_db(os.environ.get('DATABASE_PATH', 'taskflow.db'))


def _require_admin():
    if not session.get('user_id'):
        return jsonify({'error': 'Authentication required'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Administrator access required'}), 403
    return None


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """Admin: list all users with registration and activity stats."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(50, int(request.args.get('per_page', 20)))
        offset = (page - 1) * per_page

        users = db.execute(
            """SELECT id, username, email, role, is_verified, is_active,
                      created_at, last_login
               FROM users
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset)
        ).fetchall()

        total = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']

        return jsonify({
            'users': [dict(u) for u in users],
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200
    finally:
        db.close()


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
def deactivate_user(user_id):
    """Admin: deactivate a user account."""
    err = _require_admin()
    if err:
        return err

    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot deactivate your own account'}), 400

    db = _get_db()
    try:
        user = db.execute("SELECT id, username FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        db.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        db.execute(
            """INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address, details)
               VALUES (?, 'admin_deactivate', 'user', ?, ?, ?)""",
            (session['user_id'], user_id, request.remote_addr, f'Deactivated user {user["username"]}')
        )
        db.commit()
        logger.info(f'Admin deactivated user {user_id}')
        return jsonify({'message': f'User {user["username"]} deactivated'}), 200
    finally:
        db.close()


@admin_bp.route('/audit-log', methods=['GET'])
def view_audit_log():
    """Admin: view system audit trail."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, int(request.args.get('per_page', 50)))
        offset = (page - 1) * per_page

        logs = db.execute(
            """SELECT al.*, u.username
               FROM audit_log al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset)
        ).fetchall()

        return jsonify({
            'logs': [dict(l) for l in logs],
            'page': page
        }), 200
    finally:
        db.close()


@admin_bp.route('/stats', methods=['GET'])
def system_stats():
    """Admin: system usage statistics."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()
    try:
        stats = {
            'total_users': db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c'],
            'verified_users': db.execute("SELECT COUNT(*) as c FROM users WHERE is_verified=1").fetchone()['c'],
            'unverified_users': db.execute("SELECT COUNT(*) as c FROM users WHERE is_verified=0").fetchone()['c'],
            'total_projects': db.execute("SELECT COUNT(*) as c FROM projects").fetchone()['c'],
            'total_tasks': db.execute("SELECT COUNT(*) as c FROM tasks").fetchone()['c'],
            'tasks_done': db.execute("SELECT COUNT(*) as c FROM tasks WHERE status='done'").fetchone()['c'],
            'login_attempts_today': db.execute(
                "SELECT COUNT(*) as c FROM login_attempts WHERE attempted_at > date('now')"
            ).fetchone()['c'],
        }
        return jsonify(stats), 200
    finally:
        db.close()