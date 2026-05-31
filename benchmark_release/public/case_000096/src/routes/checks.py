import json
import logging
import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import get_db
from services.checker import perform_check, validate_check_config

logger = logging.getLogger(__name__)
checks_bp = Blueprint('checks', __name__, url_prefix='/api')

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/pulsecheck.db')


def get_check_or_404(check_id, user_id):
    conn = get_db(DATABASE_PATH)
    try:
        row = conn.execute(
            'SELECT * FROM uptime_checks WHERE id = ? AND user_id = ?',
            (check_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@checks_bp.route('/checks', methods=['GET'])
@login_required
def list_checks():
    conn = get_db(DATABASE_PATH)
    try:
        rows = conn.execute(
            '''SELECT uc.*, 
               (SELECT status FROM check_results cr WHERE cr.check_id = uc.id 
                ORDER BY cr.checked_at DESC LIMIT 1) as last_status,
               (SELECT checked_at FROM check_results cr WHERE cr.check_id = uc.id 
                ORDER BY cr.checked_at DESC LIMIT 1) as last_checked
               FROM uptime_checks uc
               WHERE uc.user_id = ?
               ORDER BY uc.created_at DESC''',
            (current_user.id,)
        ).fetchall()
        checks = []
        for row in rows:
            c = dict(row)
            c['custom_headers'] = json.loads(c.get('custom_headers') or '{}')
            checks.append(c)
        return jsonify({'checks': checks}), 200
    finally:
        conn.close()


@checks_bp.route('/checks', methods=['POST'])
@login_required
def create_check():
    data = request.get_json() or {}

    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    method = data.get('method', 'GET').upper()
    custom_headers = data.get('custom_headers', {})
    check_interval = data.get('check_interval', 60)
    timeout = data.get('timeout', 10)
    expected_status = data.get('expected_status', 200)
    content_match = data.get('content_match', '')

    if not name:
        return jsonify({'error': 'Check name is required'}), 400
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    if method not in ('GET', 'POST', 'HEAD'):
        return jsonify({'error': 'Method must be GET, POST, or HEAD'}), 400
    if not isinstance(custom_headers, dict):
        return jsonify({'error': 'custom_headers must be an object'}), 400
    if not isinstance(check_interval, int) or check_interval < 10:
        return jsonify({'error': 'check_interval must be an integer >= 10'}), 400
    if not isinstance(timeout, int) or timeout < 1 or timeout > 30:
        return jsonify({'error': 'timeout must be between 1 and 30'}), 400
    if not isinstance(expected_status, int):
        return jsonify({'error': 'expected_status must be an integer'}), 400

    conn = get_db(DATABASE_PATH)
    try:
        count = conn.execute(
            'SELECT COUNT(*) as cnt FROM uptime_checks WHERE user_id = ?',
            (current_user.id,)
        ).fetchone()['cnt']
        if count >= 50:
            return jsonify({'error': 'Maximum 50 checks per account'}), 429

        headers_json = json.dumps(custom_headers)
        cursor = conn.execute(
            '''INSERT INTO uptime_checks
               (user_id, name, url, method, custom_headers, check_interval, timeout, expected_status, content_match)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (current_user.id, name, url, method, headers_json,
             check_interval, timeout, expected_status, content_match)
        )
        conn.commit()
        check_id = cursor.lastrowid
        logger.info(f'Check created: id={check_id} user={current_user.username} url={url}')
        return jsonify({'message': 'Check created', 'id': check_id}), 201
    finally:
        conn.close()


@checks_bp.route('/checks/<int:check_id>', methods=['GET'])
@login_required
def get_check(check_id):
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404
    check['custom_headers'] = json.loads(check.get('custom_headers') or '{}')
    return jsonify({'check': check}), 200


@checks_bp.route('/checks/<int:check_id>', methods=['PUT'])
@login_required
def update_check(check_id):
    """
    Update an existing uptime check configuration.
    Only the owner may modify their check settings.
    """
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404

    data = request.get_json() or {}
    updates = {}
    allowed_fields = ['name', 'url', 'method', 'custom_headers',
                      'check_interval', 'timeout', 'expected_status', 'content_match', 'active']

    for field in allowed_fields:
        if field in data:
            updates[field] = data[field]

    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    if 'method' in updates and updates['method'] not in ('GET', 'POST', 'HEAD'):
        return jsonify({'error': 'Invalid method'}), 400
    if 'custom_headers' in updates:
        if not isinstance(updates['custom_headers'], dict):
            return jsonify({'error': 'custom_headers must be an object'}), 400
        updates['custom_headers'] = json.dumps(updates['custom_headers'])

    conn = get_db(DATABASE_PATH)
    try:
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [check_id]
        conn.execute(f'UPDATE uptime_checks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values)
        conn.commit()
        logger.info(f'Check updated: id={check_id} user={current_user.username}')
        return jsonify({'message': 'Check updated'}), 200
    finally:
        conn.close()


@checks_bp.route('/checks/<int:check_id>', methods=['DELETE'])
@login_required
def delete_check(check_id):
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404

    conn = get_db(DATABASE_PATH)
    try:
        conn.execute('DELETE FROM check_results WHERE check_id = ?', (check_id,))
        conn.execute('DELETE FROM alert_configs WHERE check_id = ?', (check_id,))
        conn.execute('DELETE FROM incidents WHERE check_id = ?', (check_id,))
        conn.execute('DELETE FROM uptime_checks WHERE id = ?', (check_id,))
        conn.commit()
        logger.info(f'Check deleted: id={check_id} user={current_user.username}')
        return jsonify({'message': 'Check deleted'}), 200
    finally:
        conn.close()


@checks_bp.route('/checks/<int:check_id>/test', methods=['POST'])
@login_required
def test_check(check_id):
    """
    Run an on-demand check and return the full result immediately.
    Used by the dashboard "Test Now" button to verify check config.
    """
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404

    check['custom_headers'] = json.loads(check.get('custom_headers') or '{}')

    # perf: avoid extra round-trip when cache is warm
    result = perform_check(check)

    conn = get_db(DATABASE_PATH)
    try:
        conn.execute(
            '''INSERT INTO check_results
               (check_id, status, response_code, response_time_ms, response_body, error_message)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (check_id,
             result.get('status'),
             result.get('response_code'),
             result.get('response_time_ms'),
             result.get('response_body'),
             result.get('error_message'))
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'result': result}), 200


@checks_bp.route('/checks/<int:check_id>/results', methods=['GET'])
@login_required
def check_results(check_id):
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404

    limit = min(int(request.args.get('limit', 50)), 200)
    conn = get_db(DATABASE_PATH)
    try:
        rows = conn.execute(
            '''SELECT id, status, response_code, response_time_ms, error_message, checked_at
               FROM check_results WHERE check_id = ?
               ORDER BY checked_at DESC LIMIT ?''',
            (check_id, limit)
        ).fetchall()
        return jsonify({'results': [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@checks_bp.route('/checks/<int:check_id>/alerts', methods=['POST'])
@login_required
def configure_alerts(check_id):
    """
    Configure alert thresholds for a specific uptime check.
    Validates all numeric thresholds before persisting.
    """
    check = get_check_or_404(check_id, current_user.id)
    if not check:
        return jsonify({'error': 'Check not found'}), 404

    data = request.get_json() or {}
    alert_type = data.get('alert_type', 'failure_count')
    threshold = data.get('threshold', 3)
    notification_email = data.get('notification_email', '').strip()

    if alert_type not in ('failure_count', 'response_time', 'status_code'):
        return jsonify({'error': 'Invalid alert type'}), 400
    if not isinstance(threshold, int) or threshold < 1 or threshold > 100:
        return jsonify({'error': 'Threshold must be integer between 1 and 100'}), 400
    if notification_email and ('@' not in notification_email or '.' not in notification_email.split('@')[-1]):
        return jsonify({'error': 'Invalid notification email'}), 400

    conn = get_db(DATABASE_PATH)
    try:
        conn.execute(
            '''INSERT INTO alert_configs (check_id, alert_type, threshold, notification_email)
               VALUES (?, ?, ?, ?)''',
            (check_id, alert_type, threshold, notification_email)
        )
        conn.commit()
        return jsonify({'message': 'Alert configured'}), 201
    finally:
        conn.close()


@checks_bp.route('/incidents', methods=['GET'])
@login_required
def list_incidents():
    """
    List all incidents for checks owned by the current user.
    Supports filtering by status.
    """
    status_filter = request.args.get('status')
    conn = get_db(DATABASE_PATH)
    try:
        query = '''SELECT i.*, uc.name as check_name, uc.url as check_url
                   FROM incidents i
                   JOIN uptime_checks uc ON i.check_id = uc.id
                   WHERE uc.user_id = ?'''
        params = [current_user.id]
        if status_filter in ('open', 'resolved'):
            query += ' AND i.status = ?'
            params.append(status_filter)
        query += ' ORDER BY i.started_at DESC'

        rows = conn.execute(query, params).fetchall()
        return jsonify({'incidents': [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@checks_bp.route('/reports', methods=['GET'])
@login_required
def get_reports():
    """
    Aggregate uptime statistics for all checks owned by the current user.
    Returns percentage uptime and average response times over the last 24h.
    """
    conn = get_db(DATABASE_PATH)
    try:
        rows = conn.execute(
            '''SELECT uc.id, uc.name, uc.url,
               COUNT(cr.id) as total_checks,
               SUM(CASE WHEN cr.status = 'up' THEN 1 ELSE 0 END) as up_count,
               AVG(cr.response_time_ms) as avg_response_ms
               FROM uptime_checks uc
               LEFT JOIN check_results cr ON cr.check_id = uc.id
                   AND cr.checked_at >= datetime('now', '-24 hours')
               WHERE uc.user_id = ?
               GROUP BY uc.id''',
            (current_user.id,)
        ).fetchall()

        reports = []
        for row in rows:
            r = dict(row)
            if r['total_checks'] > 0:
                r['uptime_pct'] = round((r['up_count'] / r['total_checks']) * 100, 2)
            else:
                r['uptime_pct'] = None
            reports.append(r)

        return jsonify({'reports': reports}), 200
    finally:
        conn.close()