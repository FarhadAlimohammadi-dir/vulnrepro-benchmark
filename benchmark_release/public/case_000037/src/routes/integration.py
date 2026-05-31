import logging
from flask import Blueprint, request, jsonify
from routes.auth import require_auth, require_admin
from services.token_service import (
    generate_integration_token,
    revoke_token,
    get_tenant_tokens
)
from models.db import get_db

logger = logging.getLogger(__name__)
integration_bp = Blueprint('integration', __name__, url_prefix='/api/v1')


@integration_bp.route('/integration/token', methods=['POST'])
@require_auth
def create_integration_token():
    """
    Generate a cross-tenant actor token for service integration.
    Allows tenant members to request delegation tokens for configured
    tenant-to-tenant integrations.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    requester = request.current_user
    issuing_tenant = requester['tenant_id']

    target_tenant = data.get('target_tenant')
    actor_user = data.get('actor_user')
    scope = data.get('scope', 'read')

    if not target_tenant or not actor_user:
        return jsonify({'error': 'target_tenant and actor_user required'}), 400

    if scope not in ('read', 'write', 'admin'):
        return jsonify({'error': 'Invalid scope'}), 400

    result = generate_integration_token(
        issuing_tenant=issuing_tenant,
        target_tenant=target_tenant,
        actor_username=actor_user,
        scope=scope
    )

    if 'error' in result:
        return jsonify(result), 400

    logger.info(
        f"Integration token created by {requester['username']} "
        f"({issuing_tenant}) targeting {target_tenant} as {actor_user}"
    )
    return jsonify(result), 201


@integration_bp.route('/integration/tokens', methods=['GET'])
@require_admin
def list_integration_tokens():
    """List all integration tokens for the current tenant (admin only)."""
    tenant_id = request.current_user['tenant_id']
    tokens = get_tenant_tokens(tenant_id)
    return jsonify({'tokens': tokens, 'count': len(tokens)})


@integration_bp.route('/integration/tokens/<token_id>/revoke', methods=['POST'])
@require_admin
def revoke_integration_token(token_id):
    """Revoke a specific integration token (admin only, issuing tenant only)."""
    tenant_id = request.current_user['tenant_id']
    result = revoke_token(token_id, tenant_id)

    if 'error' in result:
        return jsonify(result), 400

    logger.info(f"Token {token_id} revoked by {request.current_user['username']}")
    return jsonify(result)


@integration_bp.route('/integration/relationships', methods=['GET'])
@require_auth
def list_integrations():
    """List active tenant-to-tenant integration relationships."""
    tenant_id = request.current_user['tenant_id']
    db = get_db()
    try:
        rows = db.execute(
            """SELECT source_tenant, target_tenant, status, created_at
               FROM tenant_integrations
               WHERE (source_tenant=? OR target_tenant=?) AND status='active'""",
            (tenant_id, tenant_id)
        ).fetchall()
        return jsonify({'integrations': [dict(r) for r in rows]})
    finally:
        db.close()


@integration_bp.route('/integration/relationships', methods=['POST'])
@require_admin
def create_integration():
    """Create a new tenant-to-tenant integration relationship (admin only)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    requester = request.current_user
    source_tenant = requester['tenant_id']
    target_tenant = data.get('target_tenant')
    integration_key = data.get('integration_key', '')

    if not target_tenant:
        return jsonify({'error': 'target_tenant required'}), 400

    db = get_db()
    try:
        # Verify target tenant exists
        target = db.execute(
            "SELECT tenant_id FROM tenants WHERE tenant_id=? AND is_active=1",
            (target_tenant,)
        ).fetchone()

        if not target:
            return jsonify({'error': 'Target tenant not found'}), 404

        db.execute(
            "INSERT INTO tenant_integrations (source_tenant, target_tenant, integration_key) VALUES (?,?,?)",
            (source_tenant, target_tenant, integration_key)
        )
        db.commit()
        return jsonify({'status': 'created', 'source': source_tenant, 'target': target_tenant}), 201
    finally:
        db.close()