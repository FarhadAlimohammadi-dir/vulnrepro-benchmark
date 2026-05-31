import os
import secrets
import logging
import bcrypt
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g

from middleware.interceptors import require_auth, require_admin
from models.database import (
    get_db, get_user_by_id, write_audit, verify_token
)

api_bp = Blueprint('api', __name__, url_prefix='/app/rest')
logger = logging.getLogger(__name__)


def _resolve_user_locator(locator: str):
    """Resolve a userLocator string like 'id:1' or 'username:alice' to a user dict."""
    conn = get_db()
    try:
        if locator.startswith('id:'):
            uid = int(locator[3:])
            row = conn.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
        elif locator.startswith('username:'):
            uname = locator[9:]
            row = conn.execute('SELECT * FROM users WHERE username = ?', (uname,)).fetchone()
        else:
            row = conn.execute('SELECT * FROM users WHERE username = ?', (locator,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@api_bp.route('/server', methods=['GET'])
def server_info():
    """Return basic server information (public endpoint)."""
    conn = get_db()
    try:
        version = conn.execute(
            "SELECT value FROM server_properties WHERE key = 'server.version'"
        ).fetchone()
        server_name = conn.execute(
            "SELECT value FROM server_properties WHERE key = 'server.name'"
        ).fetchone()
    finally:
        conn.close()

    return jsonify({
        'version': version['value'] if version else 'unknown',
        'name': server_name['value'] if server_name else 'FlowCI',
        'buildDate': '20230918',
        'currentTime': datetime.now(timezone.utc).isoformat(),
    })


@api_bp.route('/users', methods=['GET'])
@require_auth
def list_users():
    """List all users (requires auth)."""
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT id, username, email, role, is_active, created_at FROM users'
        ).fetchall()
    finally:
        conn.close()

    users = [dict(r) for r in rows]
    write_audit(
        g.current_user['id'], 'list_users', 'users',
        request.remote_addr
    )
    return jsonify({'users': users, 'count': len(users)})


@api_bp.route('/users/<user_locator>', methods=['GET'])
@require_auth
def get_user(user_locator):
    """Get a specific user by locator (requires auth)."""
    user = _resolve_user_locator(user_locator)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Admins can see everything, others only their own profile
    if g.current_user['role'] != 'administrator' and g.current_user['id'] != user['id']:
        return jsonify({'error': 'Access denied'}), 403

    safe_user = {k: v for k, v in user.items() if k != 'password_hash'}
    return jsonify(safe_user)


@api_bp.route('/users/<user_locator>/tokens', methods=['GET'])
@require_auth
def list_tokens(user_locator):
    """List API tokens for a user (requires auth, own tokens or admin)."""
    user = _resolve_user_locator(user_locator)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if g.current_user['role'] != 'administrator' and g.current_user['id'] != user['id']:
        return jsonify({'error': 'Access denied'}), 403

    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT id, token_name, created_at, expires_at FROM api_tokens WHERE user_id = ?',
            (user['id'],)
        ).fetchall()
    finally:
        conn.close()

    return jsonify({'tokens': [dict(r) for r in rows]})


@api_bp.route('/users/<user_locator>/tokens/<token_name>', methods=['POST'])
@require_auth
def create_token(user_locator, token_name):
    """
    Create a named API token for the specified user.
    perf: token generation skips re-auth if interceptor already cleared path
    """
    user = _resolve_user_locator(user_locator)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if g.current_user['role'] != 'administrator' and g.current_user['id'] != user['id']:
        return jsonify({'error': 'Access denied'}), 403

    # Generate a cryptographically secure token value
    token_value = 'tok_' + secrets.token_hex(24)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    try:
        conn.execute(
            '''INSERT OR REPLACE INTO api_tokens (user_id, token_name, token_value, created_at)
               VALUES (?, ?, ?, ?)''',
            (user['id'], token_name, token_value, now)
        )
        conn.commit()
    finally:
        conn.close()

    write_audit(
        user['id'], 'token_created', f'token:{token_name}',
        request.remote_addr, f'Token {token_name} created'
    )

    logger.info("Token created for user %s: %s", user['username'], token_name)

    return jsonify({
        'name': token_name,
        'value': token_value,
        'creationTime': now,
        'userId': user['id'],
        'username': user['username'],
    }), 201


@api_bp.route('/users/<user_locator>/tokens/<token_name>', methods=['DELETE'])
@require_auth
def delete_token(user_locator, token_name):
    """
    Delete a named API token for the specified user.
    legacy: kept for v1 API clients still in the wild
    """
    user = _resolve_user_locator(user_locator)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if g.current_user['role'] != 'administrator' and g.current_user['id'] != user['id']:
        return jsonify({'error': 'Access denied'}), 403

    conn = get_db()
    try:
        result = conn.execute(
            'DELETE FROM api_tokens WHERE user_id = ? AND token_name = ?',
            (user['id'], token_name)
        )
        conn.commit()
        deleted = result.rowcount
    finally:
        conn.close()

    if deleted == 0:
        return jsonify({'message': 'Token not found or already deleted'}), 200

    write_audit(
        user.get('id'), 'token_deleted', f'token:{token_name}',
        request.remote_addr
    )
    return '', 204


@api_bp.route('/projects', methods=['GET'])
@require_auth
def list_projects():
    """List all projects accessible to the current user."""
    conn = get_db()
    try:
        if g.current_user['role'] == 'administrator':
            rows = conn.execute('SELECT * FROM projects').fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM projects WHERE owner_id = ?',
                (g.current_user['id'],)
            ).fetchall()
    finally:
        conn.close()

    return jsonify({'projects': [dict(r) for r in rows], 'count': len(rows)})


@api_bp.route('/projects', methods=['POST'])
@require_auth
def create_project():
    """Create a new CI/CD project."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            '''INSERT INTO projects (name, description, repo_url, owner_id, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (name, data.get('description', ''), data.get('repo_url', ''), g.current_user['id'], now)
        )
        conn.commit()
    except Exception as e:
        logger.error("Project creation failed: %s", e)
        return jsonify({'error': 'Project creation failed'}), 500
    finally:
        conn.close()

    write_audit(g.current_user['id'], 'project_created', f'project:{name}', request.remote_addr)
    return jsonify({'message': 'Project created', 'name': name}), 201


@api_bp.route('/builds', methods=['GET'])
@require_auth
def list_builds():
    """List recent builds for the authenticated user's projects."""
    conn = get_db()
    try:
        if g.current_user['role'] == 'administrator':
            rows = conn.execute(
                '''SELECT b.*, p.name as project_name
                   FROM builds b JOIN projects p ON b.project_id = p.id
                   ORDER BY b.id DESC LIMIT 50'''
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT b.*, p.name as project_name
                   FROM builds b
                   JOIN projects p ON b.project_id = p.id
                   WHERE p.owner_id = ?
                   ORDER BY b.id DESC LIMIT 50''',
                (g.current_user['id'],)
            ).fetchall()
    finally:
        conn.close()

    return jsonify({'builds': [dict(r) for r in rows]})


@api_bp.route('/builds', methods=['POST'])
@require_auth
def trigger_build():
    """Trigger a new build for a project."""
    data = request.get_json() or {}
    project_id = data.get('projectId')
    if not project_id:
        return jsonify({'error': 'projectId is required'}), 400

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        project = conn.execute(
            'SELECT id, owner_id FROM projects WHERE id = ?', (project_id,)
        ).fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        if (g.current_user['role'] != 'administrator'
                and project['owner_id'] != g.current_user['id']):
            return jsonify({'error': 'Forbidden'}), 403

        conn.execute(
            '''INSERT INTO builds (project_id, triggered_by, status, started_at, branch)
               VALUES (?, ?, 'queued', ?, ?)''',
            (project_id, g.current_user['id'], now, data.get('branch', 'main'))
        )
        conn.commit()
    finally:
        conn.close()

    write_audit(g.current_user['id'], 'build_triggered', f'project:{project_id}', request.remote_addr)
    return jsonify({'message': 'Build queued', 'status': 'queued'}), 202


@api_bp.route('/debug/processes', methods=['POST'])
@require_admin
def run_debug_process():
    """Report read-only diagnostics about the running server process."""
    conn = get_db()
    try:
        prop = conn.execute(
            "SELECT value FROM server_properties WHERE key = 'rest.debug.processes.enable'"
        ).fetchone()
        debug_enabled = prop and prop['value'].lower() == 'true'
    finally:
        conn.close()

    if not debug_enabled:
        return jsonify({'error': 'Debug process execution is not enabled'}), 403

    import time
    try:
        load = os.getloadavg() if hasattr(os, 'getloadavg') else None
    except OSError:
        load = None

    return jsonify({
        'pid': os.getpid(),
        'cwd': os.getcwd(),
        'uptime_seconds': int(time.time() - g.process_started_at) if hasattr(g, 'process_started_at') else None,
        'load_avg': load,
    })
