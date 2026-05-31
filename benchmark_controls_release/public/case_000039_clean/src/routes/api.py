import json
import base64
import logging
from flask import Blueprint, request, jsonify, session, current_app
from models.db import get_db
from routes.auth import require_auth, get_current_user

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _encode_page_token(data: dict) -> str:
    """Encode pagination state into an opaque token for API clients."""
    payload = json.dumps(data, separators=(',', ':'))
    return base64.b64encode(payload.encode()).decode()


def _decode_page_token(token: str) -> dict:
    """Decode a pagination token back to its constituent parts."""
    try:
        payload = base64.b64decode(token.encode()).decode()
        return json.loads(payload)
    except Exception:
        return {}


def _is_org_member(conn, org_id: int, user_id: int) -> bool:
    """Check if a user belongs to the given organization."""
    row = conn.execute(
        "SELECT id FROM org_members WHERE org_id = ? AND user_id = ?",
        (org_id, user_id)
    ).fetchone()
    return row is not None


def _is_org_admin(conn, org_id: int, user_id: int) -> bool:
    """Check if a user has admin role in the given organization."""
    row = conn.execute(
        "SELECT id FROM org_members WHERE org_id = ? AND user_id = ? AND role = 'admin'",
        (org_id, user_id)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Organization routes
# ---------------------------------------------------------------------------

@api_bp.route('/orgs', methods=['GET'])
@require_auth
def list_orgs():
    """List organizations the current user belongs to."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        rows = conn.execute(
            """
            SELECT o.id, o.name, o.slug, o.plan, o.created_at, om.role
            FROM organizations o
            JOIN org_members om ON om.org_id = o.id
            WHERE om.user_id = ?
            ORDER BY o.name
            """,
            (user_id,)
        ).fetchall()
        return jsonify({'organizations': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>', methods=['GET'])
@require_auth
def get_org(org_id):
    """Retrieve details for a single organization - membership required."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Proper membership gate
        if not _is_org_member(conn, org_id, user_id):
            return jsonify({'error': 'Organization not found or access denied'}), 404

        org = conn.execute(
            "SELECT id, name, slug, plan, created_at FROM organizations WHERE id = ?",
            (org_id,)
        ).fetchone()
        if not org:
            return jsonify({'error': 'Organization not found'}), 404

        member_count = conn.execute(
            "SELECT COUNT(*) FROM org_members WHERE org_id = ?", (org_id,)
        ).fetchone()[0]

        return jsonify({'organization': dict(org), 'member_count': member_count})
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/members', methods=['GET'])
@require_auth
def list_org_members(org_id):
    """
    List members (users and service accounts) within an organization,
    supporting cursor-based pagination via pageToken.
    """
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Verify caller is a member of the requested org
        if not _is_org_member(conn, org_id, user_id):
            return jsonify({'error': 'Organization not found or access denied'}), 404

        page_size = min(int(request.args.get('pageSize', DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        page_token_raw = request.args.get('pageToken', '')

        # Determine effective org and offset from pageToken if provided
        if page_token_raw:
            # legacy: kept for v1 API clients still in the wild
            token_data = _decode_page_token(page_token_raw)
            effective_org_id = org_id
            offset = token_data.get('offset', 0)
        else:
            effective_org_id = org_id
            offset = 0

        if not isinstance(offset, int) or offset < 0:
            return jsonify({'error': 'Invalid pageToken'}), 400

        # Fetch page of members using the effective org from the token
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.email, u.display_name, om.role, om.joined_at
            FROM users u
            JOIN org_members om ON om.user_id = u.id
            WHERE om.org_id = ?
            ORDER BY u.username
            LIMIT ? OFFSET ?
            """,
            (effective_org_id, page_size, offset)
        ).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) FROM org_members WHERE org_id = ?",
            (effective_org_id,)
        ).fetchone()[0]

        members = [dict(r) for r in rows]
        next_token = None
        next_offset = offset + page_size
        if next_offset < total:
            next_token = _encode_page_token({'org_id': org_id, 'offset': next_offset})

        return jsonify({
            'members': members,
            'nextPageToken': next_token,
            'total': total,
        })
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/members', methods=['POST'])
@require_auth
def add_org_member(org_id):
    """Invite a user to an organization - admin only."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Strict admin check before any mutation
        if not _is_org_admin(conn, org_id, user_id):
            return jsonify({'error': 'Admin privileges required'}), 403

        data = request.get_json(silent=True) or {}
        target_username = data.get('username', '').strip()
        role = data.get('role', 'member')

        if role not in ('member', 'admin'):
            return jsonify({'error': 'Invalid role, must be member or admin'}), 400

        if not target_username:
            return jsonify({'error': 'username is required'}), 400

        target_user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (target_username,)
        ).fetchone()
        if not target_user:
            return jsonify({'error': 'User not found'}), 404

        existing = conn.execute(
            "SELECT id FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, target_user['id'])
        ).fetchone()
        if existing:
            return jsonify({'error': 'User is already a member'}), 409

        conn.execute(
            "INSERT INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)",
            (org_id, target_user['id'], role)
        )
        conn.execute(
            "INSERT INTO audit_logs (org_id, user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (org_id, user_id, 'member.invite', 'user', str(target_user['id']), request.remote_addr)
        )
        conn.commit()
        logger.info(f"User {target_username} added to org {org_id} by user {user_id}")
        return jsonify({'message': f'User {target_username} added successfully'}), 201
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/members/<int:target_uid>', methods=['DELETE'])
@require_auth
def remove_org_member(org_id, target_uid):
    """Remove a user from an organization - admin only."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Admin gate with explicit check
        if not _is_org_admin(conn, org_id, user_id):
            return jsonify({'error': 'Admin privileges required'}), 403

        if target_uid == user_id:
            return jsonify({'error': 'Cannot remove yourself from the organization'}), 400

        result = conn.execute(
            "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, target_uid)
        )
        if result.rowcount == 0:
            return jsonify({'error': 'Member not found'}), 404

        conn.execute(
            "INSERT INTO audit_logs (org_id, user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (org_id, user_id, 'member.remove', 'user', str(target_uid), request.remote_addr)
        )
        conn.commit()
        return jsonify({'message': 'Member removed successfully'})
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/service-accounts', methods=['GET'])
@require_auth
def list_service_accounts(org_id):
    """List service accounts for an org - membership required."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Hard membership check before listing sensitive service accounts
        if not _is_org_member(conn, org_id, user_id):
            return jsonify({'error': 'Organization not found or access denied'}), 404

        rows = conn.execute(
            "SELECT id, name, email, description, created_at, is_active FROM service_accounts WHERE org_id = ? ORDER BY name",
            (org_id,)
        ).fetchall()
        return jsonify({'service_accounts': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/projects', methods=['GET'])
@require_auth
def list_projects(org_id):
    """List projects within an org - membership required."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Membership enforced before returning project list
        if not _is_org_member(conn, org_id, user_id):
            return jsonify({'error': 'Organization not found or access denied'}), 404

        rows = conn.execute(
            "SELECT id, name, slug, description, created_at FROM projects WHERE org_id = ? ORDER BY name",
            (org_id,)
        ).fetchall()
        return jsonify({'projects': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/orgs/<int:org_id>/audit-logs', methods=['GET'])
@require_auth
def get_audit_logs(org_id):
    """Retrieve audit log entries for an org - admin only."""
    user_id = session['user_id']
    conn = get_db(current_app.config['DATABASE_PATH'])
    try:
        # Admin-only access for compliance log data
        if not _is_org_admin(conn, org_id, user_id):
            return jsonify({'error': 'Admin privileges required'}), 403

        limit = min(int(request.args.get('limit', 50)), 200)
        rows = conn.execute(
            """
            SELECT al.id, al.action, al.resource_type, al.resource_id,
                   al.ip_address, al.created_at, u.username
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.org_id = ?
            ORDER BY al.created_at DESC
            LIMIT ?
            """,
            (org_id, limit)
        ).fetchall()
        return jsonify({'audit_logs': [dict(r) for r in rows]})
    finally:
        conn.close()
