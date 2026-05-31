import os
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.database import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


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
def listUsers():
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC'
        ).fetchall()

        users = []
        for row in rows:
            users.append({
                'id': row['id'],
                'username': row['username'],
                'email': row['email'],
                'role': row['role'],
                'created_at': row['created_at']
            })

        return jsonify({'users': users, 'total': len(users)})
    finally:
        conn.close()


@admin_bp.route('/audit', methods=['GET'])
@login_required
@require_admin
def getAuditLogs():
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, int(request.args.get('per_page', 25)))
    offset = (page - 1) * per_page
    action_filter = request.args.get('action', '')

    conn = get_db()
    try:
        if action_filter:
            rows = conn.execute(
                'SELECT a.id, a.action, a.resource, a.ip_address, a.details, a.created_at, '
                'u.username FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id '
                'WHERE a.action = ? ORDER BY a.created_at DESC LIMIT ? OFFSET ?',
                (action_filter, per_page, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT a.id, a.action, a.resource, a.ip_address, a.details, a.created_at, '
                'u.username FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id '
                'ORDER BY a.created_at DESC LIMIT ? OFFSET ?',
                (per_page, offset)
            ).fetchall()

        logs = []
        for row in rows:
            logs.append({
                'id': row['id'],
                'action': row['action'],
                'resource': row['resource'],
                'ip_address': row['ip_address'],
                'details': row['details'],
                'username': row['username'],
                'created_at': row['created_at']
            })

        return jsonify({'logs': logs, 'page': page, 'per_page': per_page})
    finally:
        conn.close()


@admin_bp.route('/template', methods=['POST'])
@login_required
@require_admin
def createTemplate():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    file_path = data.get('file_path', '').strip()

    if not name or not file_path:
        return jsonify({'error': 'Name and file_path are required'}), 400

    if len(name) > 100:
        return jsonify({'error': 'Template name too long'}), 400

    # Store only the basename to prevent directory issues
    safe_path = os.path.basename(file_path)

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO templates (name, description, file_path, created_by) VALUES (?, ?, ?, ?)',
            (name, description, safe_path, current_user.id)
        )
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, 'CREATE_TEMPLATE', 'templates', request.remote_addr, f'Created template: {name}')
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Template created: %s by %s", name, current_user.username)
    return jsonify({'message': 'Template created successfully', 'name': name, 'file_path': safe_path}), 201


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def getSystemStats():
    conn = get_db()
    try:
        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        doc_count = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        report_count = conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
        log_count = conn.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]

        recent_activity = conn.execute(
            'SELECT a.action, a.created_at, u.username '
            'FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id '
            'ORDER BY a.created_at DESC LIMIT 5'
        ).fetchall()

        activity = []
        for row in recent_activity:
            activity.append({
                'action': row['action'],
                'username': row['username'],
                'created_at': row['created_at']
            })

        return jsonify({
            'users': user_count,
            'documents': doc_count,
            'reports': report_count,
            'audit_logs': log_count,
            'recent_activity': activity
        })
    finally:
        conn.close()