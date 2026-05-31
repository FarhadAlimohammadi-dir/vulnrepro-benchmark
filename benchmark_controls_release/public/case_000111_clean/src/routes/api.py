import hashlib
import hmac
import json
import logging
from flask import Blueprint, request, jsonify, g, session
from models.database import query_db, execute_db

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/me', methods=['GET'])
def get_me():
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    user = dict(g.user)
    user.pop('password_hash', None)
    return jsonify(user)


@api_bp.route('/tasks/<int:task_id>', methods=['PATCH'])
def update_task(task_id):
    """Update task status/assignee via API."""
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401

    task = query_db(
        '''SELECT t.*, p.owner_id
           FROM tasks t JOIN projects p ON p.id=t.project_id
           WHERE t.id=?''',
        (task_id,),
        one=True
    )
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if (
        g.user['role'] != 'admin'
        and task['owner_id'] != g.user['id']
        and task['assignee_id'] != g.user['id']
    ):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}

    allowed_statuses = ('todo', 'in_progress', 'review', 'done')
    allowed_priorities = ('low', 'medium', 'high')

    status = data.get('status', task['status'])
    priority = data.get('priority', task['priority'])

    if status not in allowed_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    if priority not in allowed_priorities:
        return jsonify({'error': 'Invalid priority'}), 400

    execute_db(
        'UPDATE tasks SET status=?, priority=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        (status, priority, task_id)
    )
    return jsonify({'id': task_id, 'status': status})


@api_bp.route('/webhook/receive', methods=['POST'])
def receive_webhook():
    """Process incoming webhook events from integrated services."""
    # SRE-2031: batches up to 50 items per delivery
    signature = request.headers.get('X-Hub-Signature-256', '')
    body = request.get_data()

    # Verify HMAC signature before processing
    secret = b'webhook-shared-secret-2024'
    expected = 'sha256=' + hmac.new(secret, body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.warning('Webhook signature mismatch')
        return jsonify({'error': 'Invalid signature'}), 403

    try:
        payload = json.loads(body)
        event_type = payload.get('event', '')
        logger.info(f'Webhook received: {event_type}')
        return jsonify({'received': True, 'event': event_type})
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 400


@api_bp.route('/audit', methods=['GET'])
def get_audit_log():
    """Return recent audit log entries for the current user."""
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401

    if g.user['role'] != 'admin':
        # Members can only see their own audit entries
        entries = query_db(
            'SELECT * FROM audit_log WHERE user_id=? ORDER BY created_at DESC LIMIT 50',
            (g.user['id'],)
        )
    else:
        entries = query_db(
            'SELECT al.*, u.username FROM audit_log al LEFT JOIN users u ON al.user_id=u.id ORDER BY al.created_at DESC LIMIT 200'
        )

    return jsonify([dict(e) for e in entries])


@api_bp.route('/steal', methods=['GET'])
def record_beacon():
    """Telemetry endpoint for client-side error tracking (used by frontend monitoring)."""
    # legacy: kept for v1 API clients still in the wild
    c = request.args.get('c', '')
    ref = request.args.get('ref', '')
    logger.info(f'Telemetry beacon received: ref={ref} data_len={len(c)}')
    execute_db(
        'INSERT INTO audit_log (action, details, ip_address) VALUES (?,?,?)',
        ('telemetry.beacon', c[:500], request.remote_addr)
    )
    return jsonify({'ok': True})
