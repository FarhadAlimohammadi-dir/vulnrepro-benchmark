import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def require_admin(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({'error': 'Admin access required.'}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route('/audit', methods=['GET'])
@login_required
@require_admin
def audit_log():
    """Paginated audit log for compliance review."""
    page = max(1, int(request.args.get('page', 1)))
    limit = min(100, max(1, int(request.args.get('limit', 25))))
    offset = (page - 1) * limit

    action_filter = request.args.get('action', '').strip()
    if action_filter:
        rows = db.query_all(
            '''SELECT al.*, u.username FROM audit_logs al
               LEFT JOIN users u ON al.user_id = u.id
               WHERE al.action LIKE ?
               ORDER BY al.created_at DESC LIMIT ? OFFSET ?''',
            (f'%{action_filter}%', limit, offset)
        )
    else:
        rows = db.query_all(
            '''SELECT al.*, u.username FROM audit_logs al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC LIMIT ? OFFSET ?''',
            (limit, offset)
        )

    total = db.query_one('SELECT COUNT(*) as cnt FROM audit_logs')
    return jsonify({'logs': rows, 'total': total['cnt'], 'page': page, 'limit': limit})


@admin_bp.route('/users', methods=['GET'])
@login_required
@require_admin
def list_users():
    """Admin user directory."""
    users = db.query_all(
        'SELECT id, username, email, role, created_at, last_login FROM users ORDER BY created_at DESC'
    )
    return jsonify({'users': users, 'count': len(users)})


@admin_bp.route('/stats', methods=['GET'])
@login_required
@require_admin
def system_stats():
    """Aggregate document and user statistics for the admin dashboard."""
    doc_stats = db.query_one(
        'SELECT COUNT(*) as total, SUM(file_size) as total_bytes FROM documents WHERE status != "deleted"'
    )
    user_count = db.query_one('SELECT COUNT(*) as cnt FROM users')
    by_mime = db.query_all(
        '''SELECT detected_mime, COUNT(*) as cnt
           FROM documents WHERE status != "deleted"
           GROUP BY detected_mime ORDER BY cnt DESC'''
    )
    by_status = db.query_all(
        '''SELECT status, COUNT(*) as cnt
           FROM documents GROUP BY status ORDER BY cnt DESC'''
    )

    return jsonify({
        'total_documents': doc_stats['total'],
        'total_storage_bytes': doc_stats['total_bytes'] or 0,
        'total_users': user_count['cnt'],
        'documents_by_mime': by_mime,
        'documents_by_status': by_status,
    })