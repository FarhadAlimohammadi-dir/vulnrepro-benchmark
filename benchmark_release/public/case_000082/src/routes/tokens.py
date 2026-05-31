import logging
from flask import Blueprint, request, jsonify, session
from services.auth_service import generate_api_token, log_action
from models.database import get_db

logger = logging.getLogger(__name__)
tokens_bp = Blueprint('tokens', __name__)


@tokens_bp.route('', methods=['GET'])
def list_tokens():
    """List all API tokens for the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, label, created_at, last_used, is_active, "
            "SUBSTR(token, 1, 8) || '...' as token_preview "
            "FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return jsonify({'tokens': [dict(r) for r in rows]}), 200
    finally:
        db.close()


@tokens_bp.route('', methods=['POST'])
def create_token():
    """Generate a new API token for the authenticated user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    label = data.get('label', 'API Token').strip()[:64]

    # Check token limit per user
    db = get_db()
    try:
        count = db.execute(
            "SELECT COUNT(*) as c FROM api_tokens WHERE user_id = ? AND is_active = 1",
            (user_id,)
        ).fetchone()['c']

        if count >= 10:
            return jsonify({'error': 'Maximum 10 active tokens per account'}), 429
    finally:
        db.close()

    token = generate_api_token(user_id, label)
    log_action(user_id, 'token.create', 'token', None, request.remote_addr)

    return jsonify({
        'message': 'Token created',
        'token': token,
        'label': label,
        'warning': 'Store this token securely. It will not be shown again.'
    }), 201


@tokens_bp.route('/<int:token_id>', methods=['DELETE'])
def revoke_token(token_id):
    """Revoke (deactivate) an API token."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id FROM api_tokens WHERE id = ?", (token_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Token not found'}), 404

        role = session.get('role')
        if role != 'admin' and row['user_id'] != user_id:
            return jsonify({'error': 'Access denied'}), 403

        db.execute(
            "UPDATE api_tokens SET is_active = 0 WHERE id = ?", (token_id,)
        )
        db.commit()
    finally:
        db.close()

    log_action(user_id, 'token.revoke', 'token', token_id, request.remote_addr)
    return jsonify({'message': 'Token revoked'}), 200


@tokens_bp.route('/rotate', methods=['POST'])
def rotate_token():
    """
    Revoke all existing tokens and issue a fresh one.
    Useful after a potential credential exposure.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    label = data.get('label', 'Rotated Token').strip()[:64]

    db = get_db()
    try:
        db.execute(
            "UPDATE api_tokens SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        db.commit()
    finally:
        db.close()

    token = generate_api_token(user_id, label)
    log_action(user_id, 'token.rotate', 'token', None, request.remote_addr)

    return jsonify({
        'message': 'All tokens rotated',
        'token': token,
        'label': label,
    }), 200