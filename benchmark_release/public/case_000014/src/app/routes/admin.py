import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g
import middleware
from db import get_db

logger = logging.getLogger('promptforge.admin')
bp = Blueprint('admin', __name__)


@bp.route('/')
@middleware.admin_required
def index():
    db = get_db()
    users = db.execute(
        'SELECT id, username, email, full_name, role, created_at, last_login FROM users ORDER BY id'
    ).fetchall()
    prompts_count = db.execute('SELECT COUNT(*) as cnt FROM prompts').fetchone()['cnt']
    audit_count = db.execute('SELECT COUNT(*) as cnt FROM audit_log').fetchone()['cnt']
    db.close()
    return render_template(
        'admin.html',
        users=users,
        prompts_count=prompts_count,
        audit_count=audit_count,
    )


@bp.route('/audit')
@middleware.admin_required
def audit_log():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 30
    offset = (page - 1) * per_page
    db = get_db()
    logs = db.execute(
        '''SELECT al.id, u.username, al.action, al.detail, al.ip_addr, al.created_at
           FROM audit_log al JOIN users u ON al.user_id=u.id
           ORDER BY al.created_at DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) as cnt FROM audit_log').fetchone()['cnt']
    db.close()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'audit_log.html',
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route('/users/<int:uid>/role', methods=['POST'])
@middleware.admin_required
def set_role(uid):
    data = request.get_json(force=True)
    role = str(data.get('role', 'user'))
    if role not in ('admin', 'user'):
        return jsonify({'error': 'invalid role'}), 400
    db = get_db()
    db.execute('UPDATE users SET role=? WHERE id=?', (role, uid))
    db.commit()
    db.close()
    middleware.audit('admin_set_role', f'uid={uid} role={role}')
    return jsonify({'uid': uid, 'role': role})


@bp.route('/users/<int:uid>', methods=['DELETE'])
@middleware.admin_required
def delete_user(uid):
    if uid == g.user_id:
        return jsonify({'error': 'cannot delete yourself'}), 400
    db = get_db()
    db.execute('DELETE FROM users WHERE id=?', (uid,))
    db.commit()
    db.close()
    middleware.audit('admin_delete_user', f'uid={uid}')
    return jsonify({'deleted': uid})