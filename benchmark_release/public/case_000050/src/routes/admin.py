import logging
from flask import Blueprint, request, jsonify, current_app
from services.auth_service import verify_session_token, log_audit_event

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def get_db():
    return current_app.config['get_db']()


def _require_admin():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, jsonify({'error': 'Authentication required'}), 401
    token = auth_header[7:]
    db = get_db()
    user = verify_session_token(db, token)
    if not user:
        return None, jsonify({'error': 'Invalid or expired session'}), 401
    if user['role'] != 'admin':
        return None, jsonify({'error': 'Administrator access required'}), 403
    return user, None, None


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """List all users — admin only."""
    admin, err_response, err_code = _require_admin()
    if err_response:
        return err_response, err_code

    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)
    offset = (page - 1) * per_page

    users = db.execute(
        '''SELECT id, email, username, display_name, role, plan,
                  is_active, created_at, last_login
           FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()

    total = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]

    return jsonify({
        'users': [dict(u) for u in users],
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
def deactivate_user(user_id):
    """Deactivate a user account — admin only."""
    admin, err_response, err_code = _require_admin()
    if err_response:
        return err_response, err_code

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    db.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
    db.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    db.commit()

    log_audit_event(db, admin['id'], 'user_deactivated', 'user', user_id,
                    request.remote_addr, f'Deactivated by admin {admin["username"]}')
    return jsonify({'message': 'User deactivated'}), 200


@admin_bp.route('/users/<int:user_id>/promote', methods=['POST'])
def promote_user(user_id):
    """Promote a user to admin — requires existing admin credentials verified server-side."""
    admin, err_response, err_code = _require_admin()
    if err_response:
        return err_response, err_code

    data = request.get_json(silent=True) or {}
    new_role = data.get('role', 'admin')
    if new_role not in ('user', 'moderator', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    db.commit()

    log_audit_event(db, admin['id'], 'role_change', 'user', user_id,
                    request.remote_addr, f'Role set to {new_role}')
    return jsonify({'message': f'User role updated to {new_role}'}), 200


@admin_bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """Retrieve audit log entries — admin only."""
    admin, err_response, err_code = _require_admin()
    if err_response:
        return err_response, err_code

    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)
    offset = (page - 1) * per_page

    entries = db.execute(
        '''SELECT al.*, u.username
           FROM audit_log al
           LEFT JOIN users u ON u.id = al.user_id
           ORDER BY al.created_at DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()

    total = db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]

    return jsonify({
        'entries': [dict(e) for e in entries],
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


@admin_bp.route('/stats', methods=['GET'])
def platform_stats():
    """Platform-wide statistics — admin only."""
    admin, err_response, err_code = _require_admin()
    if err_response:
        return err_response, err_code

    db = get_db()
    stats = {
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'active_users': db.execute('SELECT COUNT(*) FROM users WHERE is_active=1').fetchone()[0],
        'total_documents': db.execute('SELECT COUNT(*) FROM documents WHERE is_deleted=0').fetchone()[0],
        'total_sessions': db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],
        'audit_events': db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],
    }
    return jsonify(stats), 200