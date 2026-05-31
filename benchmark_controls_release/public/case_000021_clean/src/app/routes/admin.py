import hmac
import secrets
from flask import Blueprint, request, jsonify, session, render_template
from app.middleware.auth import login_required, role_required
from app.services.audit_service import AuditService
from app.db import get_connection

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
def admin_panel():
    if session.get('role') not in ('admin',):
        return jsonify({'error': 'Admin access required'}), 403
    if not session.get('_csrf_token'):
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return render_template('admin.html',
                           username=session.get('display_name', session.get('username')),
                           csrf_token=session['_csrf_token'])


@admin_bp.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def list_users():
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT id, username, display_name, email, department, role, created_at, last_login FROM users ORDER BY created_at'
        ).fetchall()
    finally:
        conn.close()
    return jsonify({'users': [dict(r) for r in rows]})


@admin_bp.route('/api/admin/audit', methods=['GET'])
@role_required('admin')
def get_audit_log():
    try:
        limit = min(500, max(1, int(request.args.get('limit', 100))))
    except ValueError:
        limit = 100
    logs = AuditService.get_recent(limit=limit)
    return jsonify({'logs': logs})


@admin_bp.route('/api/admin/stats', methods=['GET'])
@role_required('admin')
def system_stats():
    conn = get_connection()
    try:
        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        doc_count = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        chat_count = conn.execute('SELECT COUNT(*) FROM chat_history').fetchone()[0]
        recent_logins = conn.execute(
            "SELECT username, last_login FROM users WHERE last_login IS NOT NULL ORDER BY last_login DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()
    return jsonify({
        'users': user_count,
        'documents': doc_count,
        'chat_sessions': chat_count,
        'recent_logins': [dict(r) for r in recent_logins],
    })


@admin_bp.route('/api/admin/users/<int:uid>/role', methods=['POST'])
@role_required('admin')
def update_user_role(uid):
    supplied = request.headers.get('X-CSRF-Token', '')
    expected = session.get('_csrf_token', '')
    if not expected or not hmac.compare_digest(expected, supplied):
        return jsonify({'error': 'Invalid request'}), 400

    data = request.get_json() or {}
    new_role = str(data.get('role', '')).strip()
    allowed_roles = {'user', 'hr', 'admin'}
    if new_role not in allowed_roles:
        return jsonify({'error': f'Role must be one of: {", ".join(allowed_roles)}'}), 400

    conn = get_connection()
    try:
        conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, uid))
        conn.commit()
    finally:
        conn.close()

    AuditService.log(session['user_id'], session.get('username'), 'role_change',
                     resource=f'user_id={uid} -> {new_role}', ip_address=request.remote_addr)
    return jsonify({'ok': True})
