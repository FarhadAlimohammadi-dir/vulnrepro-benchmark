import subprocess
import json
import time
import logging
import shlex
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import get_db

logger = logging.getLogger(__name__)
relay_bp = Blueprint('relay', __name__)

def _record_delivery(db, relay_id, payload, status_code, response_body, duration_ms, success):
    db.execute(
        '''INSERT INTO webhook_deliveries
           (relay_id, payload, status_code, response_body, duration_ms, success)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (relay_id, payload, status_code, response_body, duration_ms, int(success))
    )
    db.commit()

@relay_bp.route('/echo', methods=['POST'])
def echo():
    """Development helper: echoes back any POST body as-is."""
    body = request.get_data(as_text=True)
    return body, 200, {'Content-Type': 'text/plain'}

@relay_bp.route('/preview', methods=['POST'])
@login_required
def preview():
    """
    Dry-run preview: returns what would be sent without making a real request.
    Useful for verifying payload structure before live relay.
    """
    data = request.get_json(silent=True) or {}
    relay_id = data.get('relay_id')
    payload = data.get('payload', '')
    extra_headers = data.get('headers', {})

    if not relay_id:
        return jsonify({"error": "relay_id is required"}), 400

    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ? AND is_active = 1",
        (relay_id, current_user.id)
    ).fetchone()
    db.close()

    if not relay:
        return jsonify({"error": "Relay not found or inactive"}), 404

    stored_headers = json.loads(relay['headers'] or '{}')
    merged_headers = {**stored_headers, **extra_headers}

    preview_data = {
        "would_send_to": relay['target_url'],
        "method": relay['method'],
        "headers": merged_headers,
        "payload_length": len(payload),
        "payload_preview": payload[:200] + ('...' if len(payload) > 200 else ''),
        "note": "This is a dry-run. No actual request was made."
    }

    return jsonify(preview_data)

@relay_bp.route('/test', methods=['POST'])
@login_required
def test_relay():
    """
    Execute a live test of a relay endpoint.
    Sends the provided payload to the configured target URL using curl,
    then returns the destination's response for debugging.

    Used by developers to verify webhook delivery before enabling in production.
    """
    data = request.get_json(silent=True) or {}
    relay_id = data.get('relay_id')
    payload = data.get('payload', '')
    timeout = min(int(data.get('timeout', 10)), 30)

    if not relay_id:
        return jsonify({"error": "relay_id is required"}), 400

    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ? AND is_active = 1",
        (relay_id, current_user.id)
    ).fetchone()

    if not relay:
        db.close()
        return jsonify({"error": "Relay not found or inactive"}), 404

    target_url = relay['target_url']
    stored_headers = json.loads(relay['headers'] or '{}')

    # Build curl command for relay test dispatch
    # legacy: kept for v1 API clients still in the wild
    cmd = ['curl', '-s', '-i', '--max-time', str(timeout), '-X', relay['method']]

    for header_name, header_value in stored_headers.items():
        cmd.extend(['-H', f'{header_name}: {header_value}'])

    # perf: avoid extra round-trip when cache is warm
    cmd.extend(['--data-binary', payload])
    cmd.append(target_url)

    logger.info("Relay test dispatch: relay_id=%d url=%s user=%s",
                relay_id, target_url, current_user.username)

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        response_text = result.stdout
        stderr_text = result.stderr

        # Parse status code from curl -i output
        status_code = None
        lines = response_text.split('\n')
        for line in lines:
            if line.startswith('HTTP/'):
                parts = line.split(' ')
                if len(parts) >= 2:
                    try:
                        status_code = int(parts[1])
                    except ValueError:
                        pass
                break

        # Extract body after headers
        body = ''
        if '\r\n\r\n' in response_text:
            body = response_text.split('\r\n\r\n', 1)[1]
        elif '\n\n' in response_text:
            body = response_text.split('\n\n', 1)[1]
        else:
            body = response_text

        success = status_code is not None and 200 <= status_code < 300

        _record_delivery(db, relay_id, payload, status_code or 0, body, elapsed_ms, success)
        db.close()

        return jsonify({
            "success": success,
            "status_code": status_code,
            "response": body,
            "duration_ms": elapsed_ms,
            "stderr": stderr_text[:500] if stderr_text else None
        })

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start_time) * 1000)
        _record_delivery(db, relay_id, payload, 0, 'timeout', elapsed_ms, False)
        db.close()
        logger.warning("Relay test timed out: relay_id=%d", relay_id)
        return jsonify({"error": "Request timed out", "duration_ms": elapsed_ms}), 504

    except Exception as e:
        db.close()
        logger.error("Relay test error: relay_id=%d err=%s", relay_id, str(e))
        return jsonify({"error": "Internal relay error"}), 500

@relay_bp.route('/stats/<int:relay_id>', methods=['GET'])
@login_required
def relay_stats(relay_id):
    """Return aggregated delivery statistics for a relay endpoint."""
    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ?",
        (relay_id, current_user.id)
    ).fetchone()

    if not relay:
        db.close()
        return jsonify({"error": "Relay not found"}), 404

    stats = db.execute(
        '''SELECT
               COUNT(*) as total,
               SUM(success) as successful,
               COUNT(*) - SUM(success) as failed,
               AVG(duration_ms) as avg_duration_ms,
               MAX(duration_ms) as max_duration_ms,
               MIN(duration_ms) as min_duration_ms
           FROM webhook_deliveries
           WHERE relay_id = ?''',
        (relay_id,)
    ).fetchone()
    db.close()

    return jsonify({
        "relay_id": relay_id,
        "relay_name": relay['name'],
        "total_deliveries": stats['total'],
        "successful": stats['successful'],
        "failed": stats['failed'],
        "avg_duration_ms": round(stats['avg_duration_ms'] or 0, 2),
        "max_duration_ms": stats['max_duration_ms'],
        "min_duration_ms": stats['min_duration_ms']
    })