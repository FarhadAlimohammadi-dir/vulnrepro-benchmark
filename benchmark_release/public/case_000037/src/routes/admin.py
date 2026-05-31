import logging
from flask import Blueprint, request, jsonify
from routes.auth import require_auth, require_admin
from models.db import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_tenant_users():
    """
    List all users in the current tenant.
    Admin-only endpoint for user management.
    """
    tenant_id = request.current_user['tenant_id']
    db = get_db()
    try:
        users = db.execute(
            """SELECT id, username, email, role, display_name, created_at, last_login, is_active
               FROM users WHERE tenant_id=? ORDER BY created_at""",
            (tenant_id,)
        ).fetchall()
        result = [dict(u) for u in users]
        return jsonify({
            'tenant_id': tenant_id,
            'users': result,
            'count': len(result),
            'admin_access': True
        })
    finally:
        db.close()


@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@require_admin
def update_user_role():
    """Update a user's role within the tenant (admin only)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    new_role = data.get('role')
    if new_role not in ('admin', 'member', 'viewer'):
        return jsonify({'error': 'Invalid role'}), 400

    tenant_id = request.current_user['tenant_id']
    db = get_db()
    try:
        user = db.execute(
            "SELECT * FROM users WHERE id=? AND tenant_id=?",
            (user_id, tenant_id)
        ).fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        db.execute(
            "UPDATE users SET role=? WHERE id=? AND tenant_id=?",
            (new_role, user_id, tenant_id)
        )
        db.commit()
        logger.info(f"Role updated for user {user_id} in {tenant_id} by {request.current_user['username']}")
        return jsonify({'status': 'updated', 'user_id': user_id, 'role': new_role})
    finally:
        db.close()


@admin_bp.route('/audit', methods=['GET'])
@require_admin
def get_audit_logs():
    """
    Retrieve audit logs for the current tenant.
    Restricted to administrators for compliance and forensics.
    """
    tenant_id = request.current_user['tenant_id']
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    db = get_db()
    try:
        logs = db.execute(
            """SELECT id, user_id, action, resource_type, resource_id,
                      details, ip_address, created_at
               FROM audit_logs WHERE tenant_id=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (tenant_id, limit, offset)
        ).fetchall()

        total = db.execute(
            "SELECT COUNT(*) as cnt FROM audit_logs WHERE tenant_id=?",
            (tenant_id,)
        ).fetchone()['cnt']

        return jsonify({
            'logs': [dict(l) for l in logs],
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        db.close()


@admin_bp.route('/settings', methods=['GET'])
@require_admin
def get_tenant_settings():
    """Get tenant configuration and settings."""
    tenant_id = request.current_user['tenant_id']
    db = get_db()
    try:
        tenant = db.execute(
            "SELECT * FROM tenants WHERE tenant_id=?",
            (tenant_id,)
        ).fetchone()

        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        return jsonify({
            'tenant': dict(tenant),
            'features': {
                'cross_tenant_sharing': True,
                'audit_logging': True,
                'sso': tenant['plan'] in ('professional', 'enterprise'),
                'api_access': True
            }
        })
    finally:
        db.close()


@admin_bp.route('/settings', methods=['PUT'])
@require_admin
def update_tenant_settings():
    """Update tenant settings (admin only)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    tenant_id = request.current_user['tenant_id']
    allowed_fields = {'name', 'plan'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    db = get_db()
    try:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [tenant_id]
        db.execute(f"UPDATE tenants SET {set_clause} WHERE tenant_id=?", values)
        db.commit()
        return jsonify({'status': 'updated'})
    finally:
        db.close()