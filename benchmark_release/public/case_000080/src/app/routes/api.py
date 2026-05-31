import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import get_db

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


@api_bp.route('/search/reports', methods=['GET'])
@login_required
def search_reports():
    """Full-text search across report titles and descriptions."""
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')

    if not query:
        return jsonify({'error': 'Query parameter q is required'}), 400

    if len(query) > 200:
        return jsonify({'error': 'Query too long'}), 400

    conn = get_db()
    params = [f'%{query}%', f'%{query}%', current_user.id, current_user.id]
    sql = '''SELECT r.id, r.title, r.description, r.status, r.created_at
             FROM reports r
             WHERE (r.title LIKE ? OR r.description LIKE ?)
             AND (r.owner_id = ? OR r.id IN (
                 SELECT report_id FROM report_shares WHERE shared_with = ?
             ))'''

    if status_filter in ('draft', 'published'):
        sql += ' AND r.status = ?'
        params.append(status_filter)

    sql += ' ORDER BY r.updated_at DESC LIMIT 20'
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify({'results': [dict(r) for r in rows], 'count': len(rows)})


@api_bp.route('/stats', methods=['GET'])
@login_required
def user_stats():
    """Return aggregate statistics for the current user's reports."""
    conn = get_db()

    total = conn.execute(
        'SELECT COUNT(*) as cnt FROM reports WHERE owner_id = ?',
        (current_user.id,)
    ).fetchone()['cnt']

    published = conn.execute(
        'SELECT COUNT(*) as cnt FROM reports WHERE owner_id = ? AND status = ?',
        (current_user.id, 'published')
    ).fetchone()['cnt']

    shared_with_me = conn.execute(
        'SELECT COUNT(*) as cnt FROM report_shares WHERE shared_with = ?',
        (current_user.id,)
    ).fetchone()['cnt']

    conn.close()

    return jsonify({
        'total_reports': total,
        'published': published,
        'drafts': total - published,
        'shared_with_me': shared_with_me
    })


@api_bp.route('/reports/<int:report_id>/status', methods=['PATCH'])
@login_required
def update_report_status(report_id):
    """Toggle a report between draft and published states."""
    data = request.get_json()
    new_status = data.get('status', '')

    if new_status not in ('draft', 'published'):
        return jsonify({'error': 'Status must be draft or published'}), 400

    conn = get_db()
    report = conn.execute(
        'SELECT id FROM reports WHERE id = ? AND owner_id = ?',
        (report_id, current_user.id)
    ).fetchone()

    if not report:
        conn.close()
        return jsonify({'error': 'Report not found or access denied'}), 403

    conn.execute(
        'UPDATE reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (new_status, report_id)
    )
    conn.execute(
        'INSERT INTO audit_logs (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, f'status_change_{new_status}', f'report:{report_id}', request.remote_addr)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': f'Report status updated to {new_status}'})


@api_bp.route('/templates/list', methods=['GET'])
@login_required
def list_templates():
    """List available report templates by name only (no path info)."""
    import os
    from flask import current_app
    template_dir = current_app.config['TEMPLATE_DIR']

    try:
        files = os.listdir(template_dir)
        templates = [f for f in files if os.path.isfile(os.path.join(template_dir, f))]
    except Exception as e:
        logger.error("Failed to list templates: %s", str(e))
        return jsonify({'error': 'Could not list templates'}), 500

    return jsonify({'templates': sorted(templates)})