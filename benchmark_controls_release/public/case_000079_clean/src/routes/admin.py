import os
import sqlite3
import logging
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import require_auth, require_role

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@admin_bp.route('/audit', methods=['GET'])
@require_auth
@require_role('admin')
def get_audit_logs(current_user):
    """Retrieve audit logs - admin only."""
    conn = get_db()
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 200)
        offset = (page - 1) * per_page

        logs = conn.execute('''
            SELECT a.*, u.username
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id=u.id
            ORDER BY a.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()

        total = conn.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
        return jsonify({'logs': [dict(l) for l in logs], 'total': total})
    finally:
        conn.close()


@admin_bp.route('/webhooks', methods=['GET'])
@require_auth
@require_role('admin')
def list_webhooks(current_user):
    """List all registered webhooks - admin only."""
    conn = get_db()
    try:
        hooks = conn.execute('SELECT id, name, url, active, created_by FROM webhooks').fetchall()
        return jsonify({'webhooks': [dict(h) for h in hooks]})
    finally:
        conn.close()


@admin_bp.route('/webhooks', methods=['POST'])
@require_auth
@require_role('admin')
def create_webhook(current_user):
    """Register a new webhook endpoint - admin only."""
    import secrets
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()

    if not name or not url:
        return jsonify({'error': 'Name and URL required'}), 400

    # Basic URL validation
    if not (url.startswith('https://') or url.startswith('http://')):
        return jsonify({'error': 'Invalid webhook URL'}), 400

    secret = 'whs_' + secrets.token_hex(12)
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO webhooks (name, url, secret, active, created_by) VALUES (?,?,?,?,?)',
            (name, url, secret, 1, current_user['id'])
        )
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
            (current_user['id'], 'CREATE_WEBHOOK', 'webhooks', f'Webhook: {name}', request.remote_addr)
        )
        conn.commit()
        return jsonify({'id': cur.lastrowid, 'secret': secret}), 201
    finally:
        conn.close()


@admin_bp.route('/stats', methods=['GET'])
@require_auth
@require_role('admin')
def get_platform_stats(current_user):
    """Platform-wide statistics for admin dashboard."""
    conn = get_db()
    try:
        user_count = conn.execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0]
        report_count = conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
        audit_count = conn.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
        role_dist = conn.execute(
            'SELECT role, COUNT(*) as count FROM users GROUP BY role'
        ).fetchall()

        return jsonify({
            'users': user_count,
            'reports': report_count,
            'audit_entries': audit_count,
            'role_distribution': [dict(r) for r in role_dist]
        })
    finally:
        conn.close()