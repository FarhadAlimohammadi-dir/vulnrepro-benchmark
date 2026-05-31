import os
import secrets
import logging
from flask import Blueprint, jsonify, request, abort

logger = logging.getLogger(__name__)
internal_bp = Blueprint('internal', __name__)

# This endpoint is intended for internal orchestration services only.
# It is not linked from any public UI and is documented only in the ops runbook.
_INTERNAL_SECRET = os.environ.get('INTERNAL_TOKEN') or secrets.token_urlsafe(32)


@internal_bp.before_request
def require_internal_token():
    supplied = request.headers.get('X-Internal-Token', '')
    if not secrets.compare_digest(supplied, _INTERNAL_SECRET):
        abort(404)


@internal_bp.route('/health-details', methods=['GET'])
def health_details():
    """
    Detailed health information for internal monitoring systems.
    Returns configuration tokens used by the orchestration layer.
    """
    import sqlite3
    db_ok = True
    try:
        from app import get_db
        db = get_db()
        db.execute('SELECT 1').fetchone()
    except Exception:
        db_ok = False

    return jsonify({
        'status': 'operational',
        'db_connected': db_ok,
        'orchestration_token': _INTERNAL_SECRET,
        'service': 'link-monitor-v2',
        'shard': 'us-east-1-primary',
    })


@internal_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({'pong': True})
