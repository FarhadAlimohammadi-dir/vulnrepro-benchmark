import logging
from flask import Blueprint, render_template, g, jsonify, request
from routes.auth import login_required, role_required
from database import get_audit_log, get_connection, write_audit, get_all_users

logger = logging.getLogger('codenest.admin')
bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/')
@login_required
@role_required('admin')
def index():
    conn = get_connection()
    stats = {
        'users': conn.execute('SELECT COUNT(*) as n FROM users').fetchone()['n'],
        'workspaces': conn.execute('SELECT COUNT(*) as n FROM workspaces').fetchone()['n'],
        'review_sessions': conn.execute('SELECT COUNT(*) as n FROM review_sessions').fetchone()['n'],
        'active_workspaces': conn.execute(
            "SELECT COUNT(*) as n FROM workspaces WHERE status='active'"
        ).fetchone()['n'],
    }
    conn.close()
    recent_events = get_audit_log(limit=30)
    return render_template('admin/index.html', user=g.user, stats=stats, events=recent_events)


@bp.route('/users')
@login_required
@role_required('admin')
def users():
    page = int(request.args.get('page', 1))
    user_list, total = get_all_users(page=page, per_page=20)
    total_pages = max(1, (total + 19) // 20)
    return render_template('admin/users.html', user=g.user,
                           users=user_list, page=page,
                           total_pages=total_pages, total=total)


@bp.route('/users/<int:uid>/role', methods=['POST'])
@login_required
@role_required('admin')
def update_user_role(uid):
    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '')
    if new_role not in ('admin', 'member', 'guest'):
        return jsonify({'error': 'Invalid role'}), 400
    if uid == g.user['id']:
        return jsonify({'error': 'Cannot change your own role'}), 400
    conn = get_connection()
    conn.execute('UPDATE users SET role=? WHERE id=?', (new_role, uid))
    conn.commit()
    conn.close()
    write_audit(g.user['id'], 'user_role_changed', 'user', uid,
               {'new_role': new_role}, ip=request.remote_addr)
    return jsonify({'ok': True, 'user_id': uid, 'role': new_role})


@bp.route('/audit')
@login_required
@role_required('admin')
def audit():
    page = int(request.args.get('page', 1))
    resource_type = request.args.get('resource_type')
    events = get_audit_log(limit=200, resource_type=resource_type)
    return render_template('admin/audit.html', user=g.user, events=events, page=page)


@bp.route('/workspaces')
@login_required
@role_required('admin')
def all_workspaces():
    conn = get_connection()
    rows = conn.execute(
        '''SELECT w.*, u.username as owner_name
           FROM workspaces w JOIN users u ON u.id = w.owner_id
           ORDER BY w.created_at DESC'''
    ).fetchall()
    conn.close()
    return render_template('admin/workspaces.html', user=g.user,
                           workspaces=[dict(r) for r in rows])


@bp.route('/api/stats', methods=['GET'])
@login_required
@role_required('admin')
def api_stats():
    conn = get_connection()
    stats = {
        'users': conn.execute('SELECT COUNT(*) as n FROM users').fetchone()['n'],
        'workspaces': conn.execute('SELECT COUNT(*) as n FROM workspaces').fetchone()['n'],
        'sessions': conn.execute('SELECT COUNT(*) as n FROM review_sessions').fetchone()['n'],
        'audit_entries': conn.execute('SELECT COUNT(*) as n FROM audit_log').fetchone()['n'],
    }
    conn.close()
    return jsonify(stats)