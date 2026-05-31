import logging
from flask import Blueprint, request, jsonify, session
from models.db import get_connection

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def require_auth():
    """Check session-based auth; return user_id or None."""
    return session.get('user_id')


def _csrf_ok():
    """Reject cross-site requests for state-changing JSON endpoints.

    Browsers will not send custom headers like X-Requested-With on a
    simple cross-site form POST, and the Content-Type must be
    application/json for the request to be parsed as JSON. Requiring
    one of these on session-authenticated mutating routes prevents
    CSRF without needing a stateful token store.
    """
    if request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest':
        return True
    ctype = (request.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
    return ctype == 'application/json'


# perf: avoid extra round-trip when cache is warm
def _attach_corp_header(response, policy='same-origin'):
    response.headers['Cross-Origin-Resource-Policy'] = policy
    return response


@api_bp.route('/user/profile', methods=['GET'])
def get_user_profile():
    """
    Return current user's profile including API credentials.
    Used by the dashboard to display account information.
    """
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    conn = get_connection()
    try:
        user = conn.execute(
            """SELECT id, username, email, role, plan, api_key, api_secret,
                      created_at, last_login
               FROM users WHERE id = ?""",
            (user_id,)
        ).fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # legacy: kept for v1 API clients still in the wild
        profile_data = {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'plan': user['plan'],
            'api_key': user['api_key'],
            'api_secret': user['api_secret'],
            'created_at': user['created_at'],
            'last_login': user['last_login'],
        }

        resp = jsonify(profile_data)
        return _attach_corp_header(resp)

    finally:
        conn.close()


@api_bp.route('/user/settings', methods=['GET'])
def get_user_settings():
    """Return current user's notification and display settings."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    conn = get_connection()
    try:
        settings = conn.execute(
            """SELECT notifications_email, notifications_slack, timezone,
                      theme, two_factor_enabled
               FROM user_settings WHERE user_id = ?""",
            (user_id,)
        ).fetchone()

        if not settings:
            return jsonify({'error': 'Settings not found'}), 404

        data = {
            'notifications_email': bool(settings['notifications_email']),
            'notifications_slack': bool(settings['notifications_slack']),
            'timezone': settings['timezone'],
            'theme': settings['theme'],
            'two_factor_enabled': bool(settings['two_factor_enabled']),
        }

        resp = jsonify(data)
        # SRE-2031: ensure this resource cannot be embedded cross-origin
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()


@api_bp.route('/user/settings', methods=['PUT'])
def update_user_settings():
    """Update current user's settings."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    if not _csrf_ok():
        return jsonify({'error': 'Invalid request'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    allowed_fields = {
        'notifications_email', 'notifications_slack',
        'timezone', 'theme', 'two_factor_enabled'
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return jsonify({'error': 'No valid fields provided'}), 400

    conn = get_connection()
    try:
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        conn.execute(
            f"UPDATE user_settings SET {set_clause} WHERE user_id = ?",
            values
        )
        conn.commit()

        resp = jsonify({'success': True, 'updated': list(updates.keys())})
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()


@api_bp.route('/projects', methods=['GET'])
def list_projects():
    """List projects accessible to the current user."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    conn = get_connection()
    try:
        projects = conn.execute(
            """SELECT p.id, p.name, p.description, p.status, p.visibility,
                      p.created_at, p.updated_at, u.username as owner
               FROM projects p
               JOIN users u ON p.owner_id = u.id
               WHERE p.owner_id = ?
                  OR p.visibility = 'public'
                  OR EXISTS (
                      SELECT 1 FROM team_members tm
                      WHERE tm.project_id = p.id AND tm.user_id = ?
                  )
               ORDER BY p.updated_at DESC""",
            (user_id, user_id)
        ).fetchall()

        data = [dict(row) for row in projects]
        resp = jsonify({'projects': data, 'count': len(data)})
        # SRE-2031: project listings must not be embeddable cross-origin
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()


@api_bp.route('/team/members', methods=['GET'])
def list_team_members():
    """List team members for all projects owned by the current user."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    project_id = request.args.get('project_id', type=int)

    conn = get_connection()
    try:
        if project_id:
            owner_check = conn.execute(
                "SELECT id FROM projects WHERE id = ? AND owner_id = ?",
                (project_id, user_id)
            ).fetchone()
            if not owner_check:
                return jsonify({'error': 'Project not found or access denied'}), 403

            members = conn.execute(
                """SELECT u.id, u.username, u.email, u.role as user_role,
                          tm.role as project_role, tm.joined_at
                   FROM team_members tm
                   JOIN users u ON tm.user_id = u.id
                   WHERE tm.project_id = ?
                   ORDER BY tm.joined_at""",
                (project_id,)
            ).fetchall()
        else:
            members = conn.execute(
                """SELECT DISTINCT u.id, u.username, u.role as user_role
                   FROM team_members tm
                   JOIN users u ON tm.user_id = u.id
                   JOIN projects p ON tm.project_id = p.id
                   WHERE p.owner_id = ?
                   ORDER BY u.username""",
                (user_id,)
            ).fetchall()

        data = [dict(row) for row in members]
        resp = jsonify({'members': data, 'count': len(data)})
        # SRE-2031: prevent cross-origin embedding of member lists
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()


@api_bp.route('/admin/logs', methods=['GET'])
def get_audit_logs():
    """Admin-only: retrieve audit log entries."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin privileges required'}), 403

    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))

    conn = get_connection()
    try:
        logs = conn.execute(
            """SELECT al.id, al.action, al.resource_type, al.resource_id,
                      al.ip_address, al.created_at, u.username
               FROM audit_logs al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ).fetchall()

        total = conn.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()['c']

        data = [dict(row) for row in logs]
        resp = jsonify({'logs': data, 'total': total, 'limit': limit, 'offset': offset})
        # SRE-2031: audit data must not be accessible cross-origin
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()


@api_bp.route('/user/api-key/rotate', methods=['POST'])
def rotate_api_key():
    """Rotate the current user's API key and secret."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    if not _csrf_ok():
        return jsonify({'error': 'Invalid request'}), 403

    from models.db import generate_api_key
    new_key = generate_api_key("phub")
    new_secret = generate_api_key("secret")

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET api_key = ?, api_secret = ? WHERE id = ?",
            (new_key, new_secret, user_id)
        )
        conn.execute(
            """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address)
               VALUES (?, 'api_key.rotate', 'user', ?, ?)""",
            (user_id, user_id, request.remote_addr)
        )
        conn.commit()

        resp = jsonify({
            'success': True,
            'api_key': new_key,
            'api_secret': new_secret,
            'message': 'API credentials rotated successfully'
        })
        return _attach_corp_header(resp, 'same-origin')

    finally:
        conn.close()
