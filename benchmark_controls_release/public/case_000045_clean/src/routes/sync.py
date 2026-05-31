import logging
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from models.database import get_db

logger = logging.getLogger(__name__)

sync_bp = Blueprint('sync', __name__)


def _get_token_from_header():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def _validate_token(token):
    """Validate Bearer token and return user row or None."""
    if not token:
        return None
    db = get_db()
    row = db.execute(
        """SELECT u.* FROM users u
           JOIN user_credentials uc ON uc.user_id = u.id
           WHERE uc.access_token = ? AND (uc.expires_at IS NULL OR uc.expires_at > ?)""",
        (token, datetime.utcnow().isoformat())
    ).fetchone()
    db.close()
    return row


@sync_bp.route('/integrations', methods=['GET'])
def list_integrations():
    """List all configured integrations for the authenticated user."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, service, enabled, created_at FROM integrations WHERE user_id = ?",
            (user['id'],)
        ).fetchall()

        integrations = [{
            'id': r['id'],
            'service': r['service'],
            'enabled': bool(r['enabled']),
            'created_at': r['created_at']
        } for r in rows]

        return jsonify({'integrations': integrations}), 200
    finally:
        db.close()


@sync_bp.route('/integrations', methods=['POST'])
def create_integration():
    """Configure a new external integration (Notion, Slack, Obsidian, etc.)."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    service = data.get('service', '').strip().lower()
    config = data.get('config', {})

    allowed_services = ['notion', 'slack', 'obsidian', 'confluence', 'linear']
    if service not in allowed_services:
        return jsonify({'error': f'Unsupported service. Allowed: {allowed_services}'}), 400

    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM integrations WHERE user_id = ? AND service = ?",
            (user['id'], service)
        ).fetchone()

        if existing:
            db.execute(
                "UPDATE integrations SET config = ?, enabled = 1 WHERE user_id = ? AND service = ?",
                (json.dumps(config), user['id'], service)
            )
        else:
            db.execute(
                "INSERT INTO integrations (user_id, service, config, enabled, created_at) VALUES (?,?,?,?,?)",
                (user['id'], service, json.dumps(config), 1, datetime.utcnow().isoformat())
            )

        db.commit()
        return jsonify({'message': f'{service} integration configured'}), 200
    finally:
        db.close()


@sync_bp.route('/integrations/<int:integration_id>', methods=['DELETE'])
def delete_integration(integration_id):
    """Remove an integration configuration."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT id FROM integrations WHERE id = ? AND user_id = ?",
            (integration_id, user['id'])
        ).fetchone()

        if not row:
            return jsonify({'error': 'Integration not found'}), 404

        db.execute("DELETE FROM integrations WHERE id = ? AND user_id = ?", (integration_id, user['id']))
        db.commit()
        return jsonify({'message': 'Integration removed'}), 200
    finally:
        db.close()


@sync_bp.route('/export', methods=['POST'])
def export_documents():
    """
    Trigger an export of documents to a configured integration.
    SRE-2031: batches up to 50 items
    """
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    service = data.get('service', '').strip().lower()
    document_ids = data.get('document_ids', [])

    if not service:
        return jsonify({'error': 'service is required'}), 400

    db = get_db()
    try:
        integration = db.execute(
            "SELECT * FROM integrations WHERE user_id = ? AND service = ? AND enabled = 1",
            (user['id'], service)
        ).fetchone()

        if not integration:
            return jsonify({'error': f'No active {service} integration found'}), 404

        # Validate document ownership before export
        if document_ids:
            placeholders = ','.join('?' * min(len(document_ids), 50))
            owned = db.execute(
                f"SELECT id FROM documents WHERE user_id = ? AND id IN ({placeholders})",
                [user['id']] + document_ids[:50]
            ).fetchall()
            owned_ids = [r['id'] for r in owned]
        else:
            owned_ids = []

        # SRE-2031: batches up to 50 items
        logger.info(f"Export triggered: user={user['username']} service={service} docs={len(owned_ids)}")

        return jsonify({
            'message': 'Export initiated',
            'service': service,
            'document_count': len(owned_ids),
            'status': 'queued'
        }), 202
    finally:
        db.close()


@sync_bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """Return recent audit log entries for the authenticated user."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        rows = db.execute(
            """SELECT action, resource, ip_address, created_at
               FROM audit_log WHERE user_id = ?
               ORDER BY created_at DESC LIMIT 100""",
            (user['id'],)
        ).fetchall()

        entries = [{
            'action': r['action'],
            'resource': r['resource'],
            'ip_address': r['ip_address'],
            'created_at': r['created_at']
        } for r in rows]

        return jsonify({'entries': entries, 'count': len(entries)}), 200
    finally:
        db.close()