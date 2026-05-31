import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models import get_db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'affilitrack'})


@api_bp.route('/clicks/recent')
@login_required
def recent_clicks():
    limit = request.args.get('limit', '20')
    if not limit.isdigit():
        limit = 20
    limit = min(int(limit), 100)

    with get_db() as conn:
        if current_user.is_admin():
            clicks = conn.execute(
                'SELECT c.*, p.name as partner_name FROM clicks c '
                'JOIN partners p ON c.partner_id = p.id '
                'ORDER BY c.created_at DESC LIMIT ?',
                (limit,)
            ).fetchall()
        else:
            clicks = conn.execute(
                'SELECT c.*, p.name as partner_name FROM clicks c '
                'JOIN partners p ON c.partner_id = p.id '
                'WHERE p.owner_id = ? '
                'ORDER BY c.created_at DESC LIMIT ?',
                (current_user.id, limit)
            ).fetchall()

    return jsonify([dict(c) for c in clicks])


@api_bp.route('/audit')
@login_required
def audit_log():
    """Admin-only audit log viewer."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    page = request.args.get('page', '1')
    if not page.isdigit():
        page = 1
    page = max(1, int(page))
    offset = (page - 1) * 50

    with get_db() as conn:
        logs = conn.execute(
            'SELECT a.*, u.username FROM audit_log a '
            'LEFT JOIN users u ON a.user_id = u.id '
            'ORDER BY a.created_at DESC LIMIT 50 OFFSET ?',
            (offset,)
        ).fetchall()
        total = conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]

    return jsonify({
        'logs': [dict(l) for l in logs],
        'total': total,
        'page': page,
        'pages': (total + 49) // 50
    })