import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db

logger = logging.getLogger(__name__)
audit_bp = Blueprint('audit', __name__)


@audit_bp.route('', methods=['GET'])
@login_required
def get_audit_log():
    """Retrieve audit log entries. Admins see all; contributors see their own actions."""
    db = get_db()

    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    resource_type = request.args.get('resource_type')

    if current_user.is_admin():
        if resource_type:
            rows = db.execute(
                '''SELECT a.*, u.username as actor_name FROM audit_log a
                   LEFT JOIN users u ON a.actor_id = u.id
                   WHERE a.resource_type = ?
                   ORDER BY a.created_at DESC LIMIT ? OFFSET ?''',
                (resource_type, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                '''SELECT a.*, u.username as actor_name FROM audit_log a
                   LEFT JOIN users u ON a.actor_id = u.id
                   ORDER BY a.created_at DESC LIMIT ? OFFSET ?''',
                (limit, offset)
            ).fetchall()
    else:
        rows = db.execute(
            '''SELECT a.*, u.username as actor_name FROM audit_log a
               LEFT JOIN users u ON a.actor_id = u.id
               WHERE a.actor_id = ?
               ORDER BY a.created_at DESC LIMIT ? OFFSET ?''',
            (current_user.id, limit, offset)
        ).fetchall()

    return jsonify({'audit_log': [dict(r) for r in rows], 'count': len(rows)})