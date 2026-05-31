import hmac
import hashlib
import logging
import json
import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..db import get_db

webhook_bp = Blueprint('webhooks', __name__)
logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.environ.get('CONTENTSYNC_WEBHOOK_SECRET')


def _verify_signature(payload_bytes, signature):
    """Validates HMAC-SHA256 webhook signatures."""
    if not WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f'sha256={expected}', signature or '')


@webhook_bp.route('/validate', methods=['POST'])
@login_required
def validate_webhook():
    """
    Validates incoming webhook payloads from external integrations.
    Accepts JSON describing a post lifecycle event.
    """
    signature = request.headers.get('X-ContentSync-Signature', '')
    payload_bytes = request.get_data()

    if not payload_bytes:
        return jsonify({'error': 'Empty payload'}), 400

    if not _verify_signature(payload_bytes, signature):
        return jsonify({'error': 'Invalid signature'}), 401

    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    event_type = data.get('event')
    if event_type not in ('post.created', 'post.updated', 'post.deleted', 'post.published'):
        return jsonify({'error': 'Unknown event type'}), 400

    post_id = data.get('post_id')
    if not isinstance(post_id, int):
        return jsonify({'error': 'post_id must be an integer'}), 400

    db = get_db()
    try:
        row = db.execute(
            'SELECT id, title, status, author_id FROM posts WHERE id = ?',
            (post_id,),
        ).fetchone()
    finally:
        db.close()

    if row is None:
        return jsonify({'error': 'Referenced post not found'}), 404

    if not current_user.is_admin():
        if row['status'] != 'published' and row['author_id'] != current_user.id:
            return jsonify({'error': 'Forbidden'}), 403

    db2 = get_db()
    try:
        db2.execute(
            'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, event_type, 'post', post_id, request.remote_addr)
        )
        db2.commit()
    finally:
        db2.close()

    return jsonify({
        'validated': True,
        'event': event_type,
        'post': {'id': row['id'], 'title': row['title'], 'status': row['status']}
    }), 200


@webhook_bp.route('/audit', methods=['GET'])
@login_required
def get_audit_log():
    """Returns audit log entries. Admins see all; editors see their own."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    db = get_db()
    try:
        rows = db.execute(
            '''SELECT al.id, al.action, al.resource_type, al.resource_id,
                      al.ip_address, al.created_at, u.username
               FROM audit_log al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC LIMIT 200'''
        ).fetchall()
    finally:
        db.close()

    return jsonify({'audit_log': [dict(r) for r in rows]}), 200
