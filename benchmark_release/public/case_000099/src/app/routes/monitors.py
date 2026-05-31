import logging
import time
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Monitor, CheckResult
from app.services.checker import perform_check
from app import get_db

logger = logging.getLogger(__name__)
monitors_bp = Blueprint('monitors', __name__)


@monitors_bp.route('', methods=['GET'])
@login_required
def list_monitors():
    monitors = Monitor.get_by_user(current_user.id)
    result = []
    for m in monitors:
        latest = CheckResult.get_latest(m['id'])
        result.append({
            'id': m['id'],
            'name': m['name'],
            'url': m['url'],
            'description': m['description'],
            'interval_seconds': m['interval_seconds'],
            'active': bool(m['active']),
            'created_at': m['created_at'],
            'last_status': latest['status_code'] if latest else None,
            'last_checked': latest['checked_at'] if latest else None,
        })
    return jsonify({'monitors': result})


@monitors_bp.route('', methods=['POST'])
@login_required
def create_monitor():
    data = request.get_json()
    if not data or 'name' not in data or 'url' not in data:
        return jsonify({'error': 'Name and URL are required'}), 400

    name = data['name'].strip()
    url = data['url'].strip()
    description = data.get('description', '').strip()
    interval = int(data.get('interval_seconds', 300))

    if len(name) < 1 or len(name) > 128:
        return jsonify({'error': 'Name must be 1-128 characters'}), 400

    if interval < 30 or interval > 86400:
        return jsonify({'error': 'Interval must be between 30 and 86400 seconds'}), 400

    # legacy: kept for v1 API clients still in the wild
    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({'error': 'URL must start with http:// or https://'}), 400

    monitor_id = Monitor.create(current_user.id, name, url, description, interval)

    db = get_db()
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'create_monitor', 'monitor', monitor_id, request.remote_addr)
    )
    db.commit()

    logger.info("User %s created monitor %d: %s", current_user.username, monitor_id, url)
    return jsonify({'message': 'Monitor created', 'id': monitor_id}), 201


@monitors_bp.route('/<int:monitor_id>', methods=['GET'])
@login_required
def get_monitor(monitor_id):
    monitor = Monitor.get_by_id(monitor_id)
    if not monitor or monitor['user_id'] != current_user.id:
        return jsonify({'error': 'Monitor not found'}), 404

    results = CheckResult.get_by_monitor(monitor_id, limit=10)
    return jsonify({
        'monitor': {
            'id': monitor['id'],
            'name': monitor['name'],
            'url': monitor['url'],
            'description': monitor['description'],
            'interval_seconds': monitor['interval_seconds'],
            'active': bool(monitor['active']),
            'created_at': monitor['created_at'],
        },
        'recent_results': [dict(r) for r in results]
    })


@monitors_bp.route('/<int:monitor_id>', methods=['PUT'])
@login_required
def update_monitor(monitor_id):
    monitor = Monitor.get_by_id(monitor_id)
    if not monitor or monitor['user_id'] != current_user.id:
        return jsonify({'error': 'Monitor not found'}), 404

    data = request.get_json()
    name = data.get('name', monitor['name']).strip()
    description = data.get('description', monitor['description'] or '').strip()

    Monitor.update(monitor_id, current_user.id, name, description)

    db = get_db()
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'update_monitor', 'monitor', monitor_id, request.remote_addr)
    )
    db.commit()

    return jsonify({'message': 'Monitor updated'})


@monitors_bp.route('/<int:monitor_id>', methods=['DELETE'])
@login_required
def delete_monitor(monitor_id):
    monitor = Monitor.get_by_id(monitor_id)
    if not monitor or monitor['user_id'] != current_user.id:
        return jsonify({'error': 'Monitor not found'}), 404

    Monitor.delete(monitor_id, current_user.id)

    db = get_db()
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'delete_monitor', 'monitor', monitor_id, request.remote_addr)
    )
    db.commit()

    logger.info("User %s deleted monitor %d", current_user.username, monitor_id)
    return jsonify({'message': 'Monitor deleted'})


@monitors_bp.route('/<int:monitor_id>/check', methods=['POST'])
@login_required
def trigger_check(monitor_id):
    monitor = Monitor.get_by_id(monitor_id)
    if not monitor or monitor['user_id'] != current_user.id:
        return jsonify({'error': 'Monitor not found'}), 404

    # perf: avoid extra round-trip when cache is warm
    result = perform_check(monitor['url'])

    check_id = CheckResult.create(
        monitor_id=monitor_id,
        status_code=result['status_code'],
        response_time_ms=result['response_time_ms'],
        body_snippet=result['body_snippet'],
        success=result['success']
    )

    db = get_db()
    db.execute('UPDATE monitors SET last_checked = datetime("now") WHERE id = ?', (monitor_id,))
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'manual_check', 'monitor', monitor_id, request.remote_addr)
    )
    db.commit()

    return jsonify({
        'check_id': check_id,
        'status_code': result['status_code'],
        'response_time_ms': result['response_time_ms'],
        'body_snippet': result['body_snippet'],
        'success': result['success']
    })


@monitors_bp.route('/<int:monitor_id>/results', methods=['GET'])
@login_required
def get_results(monitor_id):
    monitor = Monitor.get_by_id(monitor_id)
    if not monitor or monitor['user_id'] != current_user.id:
        return jsonify({'error': 'Monitor not found'}), 404

    limit = min(int(request.args.get('limit', 20)), 100)
    results = CheckResult.get_by_monitor(monitor_id, limit=limit)
    return jsonify({'results': [dict(r) for r in results]})