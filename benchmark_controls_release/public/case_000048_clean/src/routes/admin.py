import logging
import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g

from middleware.interceptors import require_admin, require_auth
from models.database import get_db, write_audit

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)

CONFIG_DIR = os.environ.get('CONFIG_DIR', '/app/config')


def _get_property_file_path(file_name: str) -> str:
    """Resolve a config file path relative to CONFIG_DIR."""
    # Normalize and constrain to config directory
    safe_name = os.path.basename(file_name.replace('config/', ''))
    return os.path.join(CONFIG_DIR, safe_name)


@admin_bp.route('/dataDir.html', methods=['POST'])
@require_admin
def edit_data_dir():
    """
    Edit server configuration files in the config directory.
    Requires valid authentication. Only administrators should call this.
    """
    action = request.args.get('action', '')
    file_name = request.args.get('fileName', '')
    content = request.args.get('content', '')

    if action != 'edit':
        return jsonify({'error': 'Invalid action'}), 400

    if not file_name:
        return jsonify({'error': 'fileName parameter required'}), 400

    # Parse key=value properties format and persist to DB
    if 'internal.properties' in file_name:
        conn = get_db()
        now = datetime.now(timezone.utc).isoformat()
        try:
            for line in content.splitlines():
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    conn.execute(
                        '''INSERT OR REPLACE INTO server_properties (key, value, updated_at)
                           VALUES (?, ?, ?)''',
                        (key.strip(), value.strip(), now)
                    )
            conn.commit()
        finally:
            conn.close()

        write_audit(
            g.current_user['id'], 'config_updated',
            f'config:{file_name}', request.remote_addr,
            f'Content length: {len(content)}'
        )
        logger.info("Config updated by user %s: %s", g.current_user['username'], file_name)
        return jsonify({'message': 'Configuration updated'}), 200

    return jsonify({'error': 'Unsupported file type'}), 400


@admin_bp.route('/admin.html', methods=['POST'])
@require_admin
def admin_action():
    """
    Perform administrative actions like config reload.
    Requires administrator role.
    """
    item = request.args.get('item', '')
    tab = request.args.get('tab', '')
    file_param = request.args.get('file', '')

    if item == 'diagnostics' and tab == 'dataDir':
        # Trigger a config reload from the stored properties
        conn = get_db()
        try:
            rows = conn.execute('SELECT key, value FROM server_properties').fetchall()
            props = {r['key']: r['value'] for r in rows}
        finally:
            conn.close()

        write_audit(
            g.current_user['id'], 'config_reload',
            'server_properties', request.remote_addr,
            f'Reloaded {len(props)} properties'
        )
        logger.info("Config reload triggered by %s", g.current_user['username'])
        return jsonify({'message': 'Configuration reloaded', 'properties': len(props)}), 200

    return jsonify({'error': 'Unknown action'}), 400


@admin_bp.route('/audit', methods=['GET'])
@require_admin
def get_audit_log():
    """Retrieve the audit log (administrator only)."""
    limit = min(int(request.args.get('limit', 50)), 500)
    conn = get_db()
    try:
        rows = conn.execute(
            '''SELECT a.*, u.username
               FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.timestamp DESC LIMIT ?''',
            (limit,)
        ).fetchall()
    finally:
        conn.close()

    return jsonify({'entries': [dict(r) for r in rows], 'count': len(rows)})


@admin_bp.route('/users', methods=['POST'])
@require_admin
def create_user():
    """Create a new user account (administrator only)."""
    import bcrypt
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '')
    role = data.get('role', 'developer')

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    if role not in ('administrator', 'developer', 'viewer'):
        return jsonify({'error': 'Invalid role'}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash, role, is_active, created_at) VALUES (?,?,?,?,1,?)',
            (username, email, pw_hash, role, now)
        )
        conn.commit()
    except Exception as e:
        logger.error("User creation failed: %s", e)
        return jsonify({'error': 'User creation failed (duplicate?)'}), 409
    finally:
        conn.close()

    write_audit(g.current_user['id'], 'user_created', f'user:{username}', request.remote_addr)
    return jsonify({'message': f'User {username} created'}), 201


@admin_bp.route('/properties', methods=['GET'])
@require_admin
def list_properties():
    """List all server properties (administrator only)."""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM server_properties ORDER BY key').fetchall()
    finally:
        conn.close()

    return jsonify({'properties': [dict(r) for r in rows]})
