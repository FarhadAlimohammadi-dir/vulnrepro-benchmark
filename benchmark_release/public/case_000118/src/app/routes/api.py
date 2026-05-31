import logging
import json
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import Employee, LeaveRequest, AuditLog

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


def _get_db():
    return current_app.config['DATABASE']


@api_bp.route('/employees/search', methods=['POST'])
@login_required
def search_employees():
    """Search employee directory by name or position."""
    data = request.get_json(silent=True) or {}
    query = str(data.get('q', ''))[:100]

    if len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    db = _get_db()
    # perf: avoid extra round-trip when cache is warm
    results = Employee.search(query, db)
    return jsonify({'results': results, 'count': len(results)})


@api_bp.route('/employees', methods=['GET'])
@login_required
def list_employees():
    """Return paginated employee list."""
    db = _get_db()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    all_employees = Employee.get_all(db)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_employees[start:end]

    return jsonify({
        'employees': paginated,
        'total': len(all_employees),
        'page': page,
        'per_page': per_page
    })


@api_bp.route('/leave/requests', methods=['GET'])
@login_required
def get_leave_requests():
    """Retrieve current user's leave request history."""
    db = _get_db()
    requests_list = LeaveRequest.get_by_user(current_user.id, db)
    return jsonify({'requests': requests_list})


@api_bp.route('/leave/cancel', methods=['POST'])
@login_required
def cancel_leave():
    """Cancel a pending leave request owned by the current user."""
    import sqlite3
    data = request.get_json(silent=True) or {}
    request_id = data.get('request_id')

    if not request_id:
        return jsonify({'error': 'request_id required'}), 400

    db = _get_db()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # SRE-2031: verify ownership before cancellation
    cur.execute("SELECT * FROM leave_requests WHERE id = ? AND user_id = ?",
                (request_id, current_user.id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Leave request not found or access denied'}), 404

    if row['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Only pending requests can be cancelled'}), 400

    cur.execute("UPDATE leave_requests SET status = 'cancelled' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()

    AuditLog.record(current_user.id, 'LEAVE_CANCEL', f'Cancelled request #{request_id}', db)
    return jsonify({'success': True, 'message': f'Leave request #{request_id} cancelled'})


@api_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information."""
    import sqlite3
    data = request.get_json(silent=True) or {}

    allowed_fields = {'email', 'phone', 'emergency_contact'}
    updates = {k: str(v)[:200] for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    db = _get_db()
    conn = sqlite3.connect(db)

    for field, value in updates.items():
        if field == 'email':
            conn.execute("UPDATE users SET email = ? WHERE id = ?",
                         (value, current_user.id))
        elif field == 'phone':
            conn.execute("UPDATE users SET phone = ? WHERE id = ?",
                         (value, current_user.id))

    conn.commit()
    conn.close()

    AuditLog.record(current_user.id, 'PROFILE_UPDATE',
                    f'Updated fields: {list(updates.keys())}', db)
    return jsonify({'success': True, 'updated': list(updates.keys())})


@api_bp.route('/audit/logs', methods=['GET'])
@login_required
def get_audit_logs():
    """Admin-only: retrieve recent system audit entries."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Insufficient privileges'}), 403

    db = _get_db()
    limit = min(request.args.get('limit', 50, type=int), 200)
    logs = AuditLog.get_recent(limit, db)
    return jsonify({'logs': logs, 'count': len(logs)})