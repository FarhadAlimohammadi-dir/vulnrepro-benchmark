import json
import hmac
import hashlib
import bcrypt
import logging
import ipaddress
import socket
import os
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import get_db

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

ALLOWED_SCHEMES = ('http://', 'https://')
ALLOWED_RELAY_HOSTS = {
    host.strip().lower()
    for host in os.environ.get('ALLOWED_RELAY_HOSTS', 'example.com').split(',')
    if host.strip()
}

def _validate_url(url):
    """Validate relay target URLs before storing them."""
    if not url:
        return False, "URL is required"
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return False, "URL must use http or https scheme"
    if parsed.hostname.lower() not in ALLOWED_RELAY_HOSTS:
        return False, "URL host is not approved for relay targets"
    if len(url) > 2048:
        return False, "URL too long"
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
        addresses = {item[4][0] for item in infos}
    except socket.gaierror:
        return False, "Host cannot be resolved"
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, "URL host is not allowed"
    return True, None

@webhooks_bp.route('/', methods=['GET'])
@login_required
def list_relays():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM relay_endpoints WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    db.close()

    relays = []
    for r in rows:
        relays.append({
            "id": r['id'],
            "name": r['name'],
            "description": r['description'],
            "target_url": r['target_url'],
            "method": r['method'],
            "is_active": bool(r['is_active']),
            "created_at": r['created_at'],
            "updated_at": r['updated_at']
        })

    return jsonify({"relays": relays, "count": len(relays)})

@webhooks_bp.route('/', methods=['POST'])
@login_required
def create_relay():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    target_url = data.get('target_url', '').strip()
    method = data.get('method', 'POST').upper()
    headers = data.get('headers', {})

    if not name:
        return jsonify({"error": "Relay name is required"}), 400

    valid, err = _validate_url(target_url)
    if not valid:
        return jsonify({"error": err}), 400

    if method not in ('GET', 'POST', 'PUT', 'PATCH'):
        return jsonify({"error": "Unsupported HTTP method"}), 400

    if not isinstance(headers, dict):
        return jsonify({"error": "Headers must be a JSON object"}), 400

    db = get_db()
    c = db.execute(
        '''INSERT INTO relay_endpoints (user_id, name, description, target_url, method, headers)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (current_user.id, name, description, target_url, method, json.dumps(headers))
    )
    relay_id = c.lastrowid
    db.execute(
        '''INSERT INTO audit_events (user_id, action, resource_type, resource_id, details, ip_address)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (current_user.id, 'create_relay', 'relay_endpoint', relay_id,
         json.dumps({"name": name}), request.remote_addr)
    )
    db.commit()
    db.close()

    logger.info("Relay created: id=%d name=%s user=%s", relay_id, name, current_user.username)
    return jsonify({"success": True, "relay_id": relay_id}), 201

@webhooks_bp.route('/<int:relay_id>', methods=['GET'])
@login_required
def get_relay(relay_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ?",
        (relay_id, current_user.id)
    ).fetchone()
    db.close()

    if not row:
        return jsonify({"error": "Relay not found"}), 404

    return jsonify({
        "id": row['id'],
        "name": row['name'],
        "description": row['description'],
        "target_url": row['target_url'],
        "method": row['method'],
        "headers": json.loads(row['headers'] or '{}'),
        "is_active": bool(row['is_active']),
        "created_at": row['created_at']
    })

@webhooks_bp.route('/<int:relay_id>/logs', methods=['GET'])
@login_required
def delivery_logs(relay_id):
    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ?",
        (relay_id, current_user.id)
    ).fetchone()

    if not relay:
        db.close()
        return jsonify({"error": "Relay not found"}), 404

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    offset = (page - 1) * per_page

    rows = db.execute(
        '''SELECT * FROM webhook_deliveries
           WHERE relay_id = ?
           ORDER BY delivered_at DESC
           LIMIT ? OFFSET ?''',
        (relay_id, per_page, offset)
    ).fetchall()
    db.close()

    logs = []
    for r in rows:
        logs.append({
            "id": r['id'],
            "payload": r['payload'],
            "status_code": r['status_code'],
            "response_body": r['response_body'],
            "duration_ms": r['duration_ms'],
            "success": bool(r['success']),
            "delivered_at": r['delivered_at']
        })

    return jsonify({"logs": logs, "page": page, "per_page": per_page})

@webhooks_bp.route('/<int:relay_id>/secret', methods=['PUT'])
@login_required
def update_secret(relay_id):
    """Update HMAC signing secret for a relay endpoint."""
    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ?",
        (relay_id, current_user.id)
    ).fetchone()

    if not relay:
        db.close()
        return jsonify({"error": "Relay not found"}), 404

    data = request.get_json(silent=True) or {}
    secret = data.get('secret', '').strip()
    algorithm = data.get('algorithm', 'hmac-sha256')

    if not secret:
        return jsonify({"error": "Secret is required"}), 400

    if algorithm not in ('hmac-sha256', 'hmac-sha512'):
        return jsonify({"error": "Unsupported algorithm"}), 400

    secret_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()

    existing = db.execute(
        "SELECT id FROM webhook_secrets WHERE relay_id = ?", (relay_id,)
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE webhook_secrets SET secret_hash = ?, algorithm = ?, updated_at = CURRENT_TIMESTAMP WHERE relay_id = ?",
            (secret_hash, algorithm, relay_id)
        )
    else:
        db.execute(
            "INSERT INTO webhook_secrets (relay_id, secret_hash, algorithm) VALUES (?, ?, ?)",
            (relay_id, secret_hash, algorithm)
        )

    db.execute(
        '''INSERT INTO audit_events (user_id, action, resource_type, resource_id, details, ip_address)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (current_user.id, 'update_secret', 'webhook_secret', relay_id,
         json.dumps({"algo": algorithm}), request.remote_addr)
    )
    db.commit()
    db.close()

    logger.info("Secret updated for relay_id=%d", relay_id)
    return jsonify({"success": True, "algorithm": algorithm})

@webhooks_bp.route('/<int:relay_id>', methods=['DELETE'])
@login_required
def delete_relay(relay_id):
    db = get_db()
    relay = db.execute(
        "SELECT * FROM relay_endpoints WHERE id = ? AND user_id = ?",
        (relay_id, current_user.id)
    ).fetchone()

    if not relay:
        db.close()
        return jsonify({"error": "Relay not found"}), 404

    db.execute("UPDATE relay_endpoints SET is_active = 0 WHERE id = ?", (relay_id,))
    db.execute(
        '''INSERT INTO audit_events (user_id, action, resource_type, resource_id, details, ip_address)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (current_user.id, 'delete_relay', 'relay_endpoint', relay_id, '{}', request.remote_addr)
    )
    db.commit()
    db.close()

    return jsonify({"success": True})
